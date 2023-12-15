import datetime
import json
import os
import signal
import subprocess
import threading
import urllib.request

from hiveline.routing.servers.routing_server import RoutingServer, RoutingServerConfig
from hiveline.routing.util import ensure_directory, wait_for_line, iterate_output


class OpenTripPlannerRoutingServer(RoutingServer):
    def __init__(self, memory_gb=4, api_timeout=20, debug=False):
        self.version = "2.4.0"
        self.otp_file_name = "otp-%s-shaded.jar" % self.version
        self.memory_gb = memory_gb
        self.api_timeout = api_timeout
        self.process = None  # instantiated when server is started
        self.debug_thread: threading.Thread | None = None
        self.err_thread: threading.Thread | None = None
        self.debug = debug

    def build(self, config: RoutingServerConfig, force_rebuild=False):
        graphs_path = _get_graphs_path(config)
        bin_path = _get_bin_path(config)

        _clean_up_graph_file(bin_path, graphs_path)
        self.__ensure_otp_downloaded(bin_path)

        graph_file = graphs_path + "/" + config.graph_id + "-graph.obj"

        if os.path.isfile(graph_file) and not force_rebuild:
            return [graph_file]

        if os.path.isfile(graph_file):
            os.remove(graph_file)

        _use_build_config(bin_path, config.osm_files, config.gtfs_files, config.target_date)

        print("Building graph...")
        result = subprocess.run(
            ["java", "-Xmx" + str(self.memory_gb) + "G", "-jar", bin_path + "/" + self.otp_file_name, "--build",
             "--save", bin_path + "/"])
        print("Done")
        print(json.dumps(result.__dict__))

        if not os.path.isfile(bin_path + "/graph.obj"):
            raise Exception("Graph not built")

        print("Graph built")
        # move to data directory
        _ensure_graphs_directory(graphs_path)

        os.rename(bin_path + "/graph.obj", graph_file)

        return [graph_file]

    def start(self, config, built_files):
        bin_path = _get_bin_path(config)
        graphs_path = _get_graphs_path(config)

        _clean_up_graph_file(bin_path, graphs_path)
        self.__ensure_otp_downloaded(bin_path)
        _ensure_graphs_directory(graphs_path)

        graph_file = built_files[0]

        if not os.path.isfile(graph_file):
            print("Graph file not found")
            return None

        print("Moving graph file...")
        os.rename(graph_file, bin_path + "/graph.obj")

        _use_run_config(bin_path, self.api_timeout)

        # store graph file name prefix
        graph_file_prefix = os.path.basename(graph_file).rstrip("-graph.obj")

        with open(bin_path + "/graph-source.json", "w", encoding="utf-8") as f:
            json.dump({
                "source": graph_file_prefix
            }, f)

        print("Starting server...")

        self.process = subprocess.Popen(
            ["java", "-Xmx" + str(self.memory_gb) + "G", "-jar", bin_path + "/" + self.otp_file_name, "--load",
             bin_path + "/"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, encoding="utf-8",
            shell=True)

        if self.process is None:
            print("Server not started")
            exit(1)

        try:
            print("Starting up server...")
            wait_for_line(self.process,
                          "Grizzly server running.")  # that is the last line printed by the server when it is ready

            self.debug_thread = threading.Thread(target=iterate_output, args=(self.process.stdout, self.debug, "[otp.out] "))
            self.debug_thread.start()

            self.err_thread = threading.Thread(target=iterate_output, args=(self.process.stderr, True, "[otp.err] "))
            self.err_thread.start()

            print("Server started")
        except Exception as e:
            print("Server startup failed")
            print(e)
            self.stop()

    def stop(self):
        if self.process is not None:
            print("Terminating server...")

            try:
                os.kill(self.process.pid, signal.CTRL_C_EVENT)  # clean shutdown with CTRL+C

                self.process.wait()
            except KeyboardInterrupt:
                pass

            print("Server terminated")
            self.process = None

        if self.debug_thread is not None:
            self.debug_thread.join()
            self.debug_thread = None

        if self.err_thread is not None:
            self.err_thread.join()
            self.err_thread = None

    def get_meta(self):
        return {
            "name": "OpenTripPlanner",
            "version": self.version
        }

    def __ensure_otp_downloaded(self, bin_path):
        """
        Ensures that the OTP jar file is downloaded.
        :return:
        """
        ensure_directory(bin_path)

        if not os.path.isfile(bin_path + "/" + self.otp_file_name):
            path = "https://repo1.maven.org/maven2/org/opentripplanner/otp/" + self.version + "/" + self.otp_file_name
            print("Downloading " + path)

            urllib.request.urlretrieve(path, bin_path + "/" + self.otp_file_name)


def _get_bin_path(config: RoutingServerConfig):
    return config.data_dir + "/opentripplanner/bin"


def _get_graphs_path(config: RoutingServerConfig):
    return config.data_dir + "/opentripplanner/graphs"


def _use_build_config(bin_path: str, osm_files: list[str], gtfs_files: list[str], target_date: datetime.date):
    """
    Updates the build config file based on the given OSM and GTFS files.
    :param osm_files: A list of OSM files
    :param gtfs_files: A list of GTFS files
    :param target_date: The target date (build process will limit transit service period to +/- 1 year)
    :return:
    """
    # convert to absolute paths
    osm_files = ["file:///" + os.path.abspath(f).replace("\\", "/") for f in osm_files]
    gtfs_files = ["file:///" + os.path.abspath(f).replace("\\", "/") for f in gtfs_files]

    # limit transit service period to +/- 1 year
    min_date = (target_date - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    max_date = (target_date + datetime.timedelta(days=365)).strftime("%Y-%m-%d")

    build_config = {
        "osm": [{"source": f} for f in osm_files],
        "transitFeeds": [{"type": "gtfs", "source": f} for f in gtfs_files],
        "transitServiceStart": min_date,
        "transitServiceEnd": max_date,
        "transitModelTimeZone": "Europe/Berlin",
    }

    ensure_directory(bin_path)

    config_file_name = bin_path + "/build-config.json"

    with open(config_file_name, "w", encoding="utf-8") as f:
        json.dump(build_config, f)


def _use_run_config(bin_path, api_processing_timeout=20):
    """
    Updates the run config file based on the parameters given
    :param api_processing_timeout: The timeout for the API processing step, in seconds
    :return:
    """

    run_config = {
        "server": {
            "apiProcessingTimeout": str(api_processing_timeout) + "s"
        }
    }

    with open(bin_path + "/router-config.json", "w") as f:
        json.dump(run_config, f)


def _ensure_graphs_directory(graphs_path):
    """
    Ensures that the data directory exists.
    :return:
    """
    ensure_directory(graphs_path)


def _clean_up_graph_file(bin_path, graphs_path):
    """
    Cleans up the graph file. If the routing algorithm did not move the graph file back, it will just stay in the bin
    directory, so we move it back in this case. If we can't figure out where it came from, it will be deleted.
    :return:
    """
    _ensure_graphs_directory(bin_path)

    if not os.path.isfile(bin_path + "/graph.obj"):
        return

    if not os.path.isfile(bin_path + "/graph-source.json"):
        os.remove(bin_path + "/graph.obj")
        return

    with open(bin_path + "/graph-source.json", "r") as f:
        source = json.load(f)["source"]
        os.rename(bin_path + "/graph.obj", graphs_path + "/" + source + "-graph.obj")
    os.remove(bin_path + "/graph-source.json")
    print("Cleaned up graph file")
