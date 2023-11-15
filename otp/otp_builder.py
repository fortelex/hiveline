import hashlib
import json
import os
import subprocess
import urllib.request

version = "2.4.0"
file_name = "otp-" + version + "-shaded.jar"


def __ensure_directory(path):
    """
    Ensures that the given directory exists. If it does not exist, it will be created.
    :param path: The path to the directory
    :return:
    """
    if not os.path.isdir(path):
        os.mkdir(path)


def __ensure_otp_downloaded():
    """
    Ensures that the OTP jar file is downloaded.
    :return:
    """
    __ensure_directory("otp/bin")

    if not os.path.isfile("otp/bin/" + file_name):
        path = "https://repo1.maven.org/maven2/org/opentripplanner/otp/" + version + "/" + file_name
        print("Downloading " + path)

        urllib.request.urlretrieve(path, "otp/bin/" + file_name)


def __ensure_data_directory():
    """
    Ensures that the data directory exists.
    :return:
    """
    __ensure_directory("otp/data")


def __clean_up_graph_file():
    """
    Cleans up the graph file. If the routing algorithm did not move the graph file back, it will just stay in the bin
    directory, so we move it back in this case. If we can't figure out where it came from, it will be deleted.
    :return:
    """
    __ensure_data_directory()

    if not os.path.isfile("otp/bin/graph.obj"):
        return

    if not os.path.isfile("otp/bin/graph-source.json"):
        os.remove("otp/bin/graph.obj")
        return

    with open("otp/bin/graph-source.json", "r") as f:
        source = json.load(f)["source"]
        os.rename("otp/bin/graph.obj", "otp/data/" + source + "-graph.obj")
    os.remove("otp/bin/graph-source.json")
    print("Cleaned up graph file")


def __get_closest_link(link_list, target_date):
    """
    Returns the link that is closest to the target date.
    :param link_list: A list of objects, each with a link and a date
    :param target_date: The target date
    :return: The closest link, or None if no link was found
    """
    if link_list is None or len(link_list) == 0:
        return None

    min_dist = None
    min_dist_index = None

    for i in range(len(link_list)):
        link = link_list[i]
        dist = abs(link["date"] - target_date)
        if min_dist is None or dist < min_dist:
            min_dist = dist
            min_dist_index = i

    if min_dist is None:
        return None

    return link_list[min_dist_index]


def __ensure_data_downloaded(link_object, file_name_extension):
    """
    Ensures that the data file is downloaded.
    :param link_object: The link object. Must have a "link" key.
    :param file_name_extension: The file name extension, including the dot
    :return: The file name of the downloaded file
    """
    if link_object is None:
        return None
    link = link_object["link"]
    link_hash = hashlib.sha3_256(link.encode()).hexdigest()

    __ensure_data_directory()

    target_file_name = "otp/data/" + link_hash + file_name_extension
    if os.path.isfile(target_file_name):
        return target_file_name

    print("Downloading " + link)
    urllib.request.urlretrieve(link, target_file_name)

    return target_file_name


def __ensure_closest_pbf_downloaded(place, target_date):
    """
    Ensures that the closest OSM file to a target date is downloaded.
    :param place: The place resource object. Must have an "osm" key.
    :param target_date: The target date
    :return: file: The file name of the downloaded file, source: The source of the file, date: The date of the file
             None if no OSM file was found
    """
    closest_osm_link = __get_closest_link(place["osm"], target_date)
    if closest_osm_link is None:
        print("No OSM link found")
        return None

    print(closest_osm_link)

    closest_osm_file = __ensure_data_downloaded(closest_osm_link, ".pbf")
    return {
        "file": closest_osm_file,
        "source": closest_osm_link["link"],
        "date": closest_osm_link["date"]
    }


def __ensure_closest_gtfs_downloaded(place, target_date):
    """
    Ensures that the closest GTFS file to a target date is downloaded.
    :param place: The place resource object. Must have a "gtfs" key.
    :param target_date: The target date
    :return: file: The file name of the downloaded file, source: The source of the file, date: The date of the file
             None if no GTFS file was found
    """
    closest_gtfs_link = __get_closest_link(place["gtfs"], target_date)
    if closest_gtfs_link is None:
        print("No GTFS link found")
        return None

    print(closest_gtfs_link)

    closest_gtfs_file = __ensure_data_downloaded(closest_gtfs_link, ".gtfs.zip")
    return {
        "file": closest_gtfs_file,
        "source": closest_gtfs_link["link"],
        "date": closest_gtfs_link["date"]
    }


def __use_build_config(osm_files, gtfs_files):
    """
    Updates the build config file based on the given OSM and GTFS files.
    :param osm_files: A list of OSM files
    :param gtfs_files: A list of GTFS files
    :return:
    """
    # convert to absolute paths
    osm_files = ["file:///" + os.path.abspath(f).replace("\\", "/") for f in osm_files]
    gtfs_files = ["file:///" + os.path.abspath(f).replace("\\", "/") for f in gtfs_files]

    config = {
        "osm": [{"source": f} for f in osm_files],
        "transitFeeds": [{"type": "gtfs", "source": f} for f in gtfs_files],
    }

    __ensure_directory("otp/bin")

    config_file_name = "otp/bin/build-config.json"

    with open(config_file_name, "w", encoding="utf-8") as f:
        json.dump(config, f)


def build_graph(place, target_date, force_rebuild=False):
    """
    Builds the graph for the given place and target date. If the graph already exists, it will not be rebuilt, unless
    force_rebuild=True.
    :param place: The place resource object
    :param target_date: The target date
    :param force_rebuild: If True, the graph will be rebuilt even if it already exists
    :return: otp_version: The version of OTP used, graph_file: The file name of the graph, osm_source: The resource
             object of the OSM file, gtfs_source: The resource object of the GTFS file
    """
    __clean_up_graph_file()

    graph_file = "./otp/data/" + place["place-id"] + "-" + target_date.isoformat().replace(":", "") + "-graph.obj"

    __ensure_otp_downloaded()

    osm_resource = __ensure_closest_pbf_downloaded(place, target_date)
    gtfs_resource = __ensure_closest_gtfs_downloaded(place, target_date)

    if os.path.isfile(graph_file) and not force_rebuild:
        print("Graph already built")
        return {
            "otp_version": version,
            "graph_file": graph_file,
            "osm_source": osm_resource,
            "gtfs_source": gtfs_resource
        }

    if os.path.isfile(graph_file):
        os.remove(graph_file)

    if osm_resource is None or gtfs_resource is None:
        print("No data found")
        return None

    __use_build_config([osm_resource["file"]], [gtfs_resource["file"]])

    print("Building graph...")
    subprocess.run(["java", "-Xmx4G", "-jar", "otp/bin/" + file_name, "--build", "--save", "./otp/bin/"])
    print("Done")

    if not os.path.isfile("./otp/bin/graph.obj"):
        print("Graph not built")
        return None

    print("Graph built")
    # move to data directory
    __ensure_directory("otp/data")

    os.rename("./otp/bin/graph.obj", graph_file)
    return {
        "otp_version": version,
        "graph_file": graph_file,
        "osm_source": osm_resource,
        "gtfs_source": gtfs_resource
    }


def run_server(graph_file):
    """
    Runs the OTP server with the given graph file. You can use build_graph to build the graph file. It will use
    Popen to run the server, so you can use the returned process object to terminate the server.
    :param graph_file: The path to the graph file
    :return: The process object of the server
    """
    __clean_up_graph_file()
    __ensure_otp_downloaded()
    __ensure_data_directory()

    if not os.path.isfile(graph_file):
        print("Graph file not found")
        return None

    print("Moving graph file...")
    os.rename(graph_file, "./otp/bin/graph.obj")

    # store graph file name prefix
    graph_file_prefix = os.path.basename(graph_file).rstrip("-graph.obj")

    with open("otp/bin/graph-source.json", "w", encoding="utf-8") as f:
        json.dump({
            "source": graph_file_prefix
        }, f)

    print("Starting server...")
    return subprocess.Popen(["java", "-Xmx4G", "-jar", "otp/bin/" + file_name, "--load", "./otp/bin/"],
                            stdout=subprocess.PIPE, text=True, encoding="utf-8")

