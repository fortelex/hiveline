import json
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.request

from hiveline.routing.servers.routing_server import RoutingServer, RoutingServerConfig
from hiveline.routing.util import ensure_directory, wait_for_line, iterate_output


class BifrostRoutingServer(RoutingServer):
    def __init__(self, threads=12, debug=False):
        self.version = "1.0.6"
        self.threads = threads
        self.file_name = "server-" + self.version
        self.download_url = "https://github.com/Vector-Hector/bifrost/releases/download/v" + self.version + "/server"
        if platform.system() == "Windows":
            self.file_name += ".exe"
            self.download_url += ".exe"
        self.process = None  # instantiated when server is started
        self.debug_thread: threading.Thread | None = None
        self.err_thread: threading.Thread | None = None
        self.debug = debug

    def build(self, config: RoutingServerConfig, force_rebuild=False) -> list[str]:
        graphs_path = _get_graphs_path(config)
        bin_path = _get_bin_path(config)

        self.__ensure_bifrost_downloaded(bin_path)

        ensure_directory(graphs_path)

        graph_file = graphs_path + "/" + config.graph_id + "-graph.bifrost"

        if os.path.isfile(graph_file) and not force_rebuild:
            return [graph_file]

        if os.path.isfile(graph_file):
            os.remove(graph_file)

        cmd = [bin_path + "/" + self.file_name, "-only-build", "-bifrost", graph_file]

        if config.osm_files:
            for osm_file in config.osm_files:
                cmd.append("-osm")
                cmd.append(osm_file)

        if config.gtfs_files:
            for gtfs_file in config.gtfs_files:
                cmd.append("-gtfs")
                cmd.append(gtfs_file)

        print("Building graph...")

        result = subprocess.run(cmd)

        print("Done")
        print(json.dumps(result.__dict__))

        if not os.path.isfile(graph_file):
            raise Exception("Graph not built")

        return [graph_file]

    def start(self, config: RoutingServerConfig, built_files: list[str]):
        bin_path = _get_bin_path(config)

        self.__ensure_bifrost_downloaded(bin_path)

        graph_file = built_files[0]

        if not os.path.isfile(graph_file):
            print("Graph file not found")
            return None

        cmd = [bin_path + "/" + self.file_name, "-threads", str(self.threads), "-bifrost", graph_file]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, encoding="utf-8")

        if self.process is None:
            print("Failed to start Bifrost")
            return None

        try:
            print("Starting up server...")
            wait_for_line(self.process, "Listening and serving HTTP on")

            self.debug_thread = threading.Thread(target=iterate_output, args=(self.process.stdout, self.debug, "[bifrost.out] "))
            self.debug_thread.start()

            self.err_thread = threading.Thread(target=iterate_output, args=(self.process.stderr, True, "[bifrost.err] "))
            self.err_thread.start()

            print("Server started")
        except Exception as e:
            print("Failed to start Bifrost: " + str(e))
            self.stop()

    def stop(self):
        if self.process:
            self.process.kill()
        self.process = None
        if self.debug_thread:
            self.debug_thread.join()
        self.debug_thread = None
        if self.err_thread:
            self.err_thread.join()
        self.err_thread = None

    def get_meta(self):
        return {
            "name": "Bifrost",
            "version": self.version,
        }

    def __ensure_bifrost_downloaded(self, bin_path):
        ensure_directory(bin_path)

        if not os.path.isfile(bin_path + "/" + self.file_name):
            print("Downloading Bifrost...")
            urllib.request.urlretrieve(self.download_url, bin_path + "/" + self.file_name)
            print("Done downloading Bifrost")

        if not os.path.isfile(bin_path + "/" + self.file_name):
            raise Exception("Bifrost not downloaded")

        if platform.system() != "Windows":
            os.chmod(bin_path + "/" + self.file_name, 0o755)


def _get_bin_path(config: RoutingServerConfig):
    return config.data_dir + "/bifrost/bin"


def _get_graphs_path(config: RoutingServerConfig):
    return config.data_dir + "/bifrost/graphs"
