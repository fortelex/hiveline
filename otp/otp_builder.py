import argparse
import hashlib
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timedelta

import bson

import gtfs_consistency
from mongo.mongo import get_database

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


def __get_closest_link(link_list, target_date, ignore_future=False):
    """
    Returns the link that is closest to the target date.
    :param link_list: A list of objects, each with a link and a date
    :param target_date: The target date
    :param ignore_future: If true, links in the future of the target date will be ignored
    :return: The closest link, or None if no link was found
    """
    if link_list is None or len(link_list) == 0:
        return None

    min_dist = None
    min_dist_index = None

    for i in range(len(link_list)):
        link = link_list[i]
        if ignore_future and link["date"] > target_date:
            continue
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
    :return: list of objects with fields:
             file: The file name of the downloaded file, source: The source of the file, date: The date of the file
    """
    links = []

    for provider, link_list in place["gtfs"].items():
        closest_gtfs_link = __get_closest_link(link_list, target_date, True)
        if closest_gtfs_link is None:
            continue

        print(closest_gtfs_link)

        closest_gtfs_file = __ensure_data_downloaded(closest_gtfs_link, ".gtfs.zip")

        # fix inconsistencies
        gtfs_consistency.fix_gtfs(closest_gtfs_file)

        links.append({
            "file": closest_gtfs_file,
            "source": closest_gtfs_link["link"],
            "date": closest_gtfs_link["date"],
            "provider": provider
        })

    return links


def __use_build_config(osm_files, gtfs_files, target_date):
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
    min_date = (target_date - timedelta(days=365)).strftime("%Y-%m-%d")
    max_date = (target_date + timedelta(days=365)).strftime("%Y-%m-%d")

    config = {
        "osm": [{"source": f} for f in osm_files],
        "transitFeeds": [{"type": "gtfs", "source": f} for f in gtfs_files],
        "transitServiceStart": min_date,
        "transitServiceEnd": max_date,
        "transitModelTimeZone": "Europe/Berlin",
    }

    __ensure_directory("otp/bin")

    config_file_name = "otp/bin/build-config.json"

    with open(config_file_name, "w", encoding="utf-8") as f:
        json.dump(config, f)


def build_graph(place, target_date, force_rebuild=False, memory_gb=4):
    """
    Builds the graph for the given place and target date. If the graph already exists, it will not be rebuilt, unless
    force_rebuild=True.
    :param place: The place resource object
    :param target_date: The target date
    :param force_rebuild: If True, the graph will be rebuilt even if it already exists
    :param memory_gb: The amount of memory to use for the graph build process
    :return: otp_version: The version of OTP used, graph_file: The file name of the graph, osm_source: The resource
             object of the OSM file, gtfs_sources: An array of resource objects of the GTFS files
    """
    __clean_up_graph_file()

    # place-id is bson.ObjectId
    place_ids = place["place-id"]
    if not isinstance(place_ids, list):
        place_ids = [place_ids]

    place_id_str = [str(place_id) for place_id in place_ids]

    print("Building graph for " + place_id_str[0] + " on " + target_date.isoformat())
    print(place)

    graph_files = ["./otp/data/" + place_id + "-" + target_date.isoformat().replace(":", "") + "-graph.obj" for place_id in place_id_str]

    __ensure_otp_downloaded()

    osm_resource = __ensure_closest_pbf_downloaded(place, target_date)
    gtfs_resources = __ensure_closest_gtfs_downloaded(place, target_date)

    print("OSM resource: " + str(osm_resource))
    print("GTFS resources: " + str(gtfs_resources))

    for graph_file in graph_files:
        if os.path.isfile(graph_file) and not force_rebuild:
            print("Graph already built")
            return {
                "otp_version": version,
                "graph_file": graph_file,
                "osm_source": osm_resource,
                "gtfs_sources": gtfs_resources
            }

    graph_file = graph_files[0]

    if os.path.isfile(graph_file):
        os.remove(graph_file)

    if osm_resource is None or gtfs_resources is None or len(gtfs_resources) == 0:
        print("No data found")
        return None

    __use_build_config([osm_resource["file"]], [gtfs_resource["file"] for gtfs_resource in gtfs_resources], target_date)

    print("Building graph...")
    subprocess.run(
        ["java", "-Xmx" + str(memory_gb) + "G", "-jar", "otp/bin/" + file_name, "--build", "--save", "./otp/bin/"])
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
        "gtfs_sources": gtfs_resources
    }


def run_server(graph_file, memory_gb=4):
    """
    Runs the OTP server with the given graph file. You can use build_graph to build the graph file. It will use
    Popen to run the server, so you can use the returned process object to terminate the server.
    :param graph_file: The path to the graph file
    :param memory_gb: The amount of memory to use for the server
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
    return subprocess.Popen(
        ["java", "-Xmx" + str(memory_gb) + "G", "-jar", "otp/bin/" + file_name, "--load", "./otp/bin/"],
        stdout=subprocess.PIPE, text=True, encoding="utf-8")


def build_common(force_rebuild=False, memory_gb=4):
    common = {
        "655740035f853dcf81ec7864": [  # paris
            "2019-10-08",  # 2019-10-08T08:00:00Z  (don't specify time zone in database)
            "2020-10-06"
        ],
        "65577e2f13f29b36636703ef": [  # dublin (alternative: 65577f5713f29b36636703f2)
            "2019-10-08",
            "2020-10-06"
        ],
        "6557841a13f29b36636703f7": [  # berlin
            "2017-10-10",
            "2018-10-09",
            "2019-10-08",
        ],
        #"": [  # hamburg
        #    "2022-10-04",
        #],
        "655a1771868acf560d1406b6": [  # leuven
            "2019-10-08",
        ],
        "65589e7810b22a1200bd253e": [  # vienna
            "2019-10-08",
        ]
    }

    database = get_database()
    place_resources = database["place-resources"]

    for place_id, dates in common.items():
        place = place_resources.find_one({"place-id": bson.ObjectId(place_id)})

        if place is None:
            print("Place not found. Skipping... (ID: " + place_id + ")")
            continue

        for target_date in dates:
            try:
                date = datetime.strptime(target_date + "T08:00", "%Y-%m-%dT%H:%M")

                print("Building graph for " + place_id + " on " + date.isoformat())

                graph = build_graph(place, date, force_rebuild, memory_gb)

                if graph is None:
                    continue

                print(graph)
            except Exception as e:
                print(e)
                print("Failed to build graph for " + place_id + " on " + target_date)


def build_single(date, place_id, force_rebuild=False, memory_gb=4):
    date = datetime.strptime(date + "T08:00", "%Y-%m-%dT%H:%M")

    print("Building graph for " + place_id + " on " + date.isoformat())

    database = get_database()
    place = database["place-resources"].find_one({"place-id": bson.ObjectId(place_id)})

    if place is None:
        print("Place not found")
        exit(1)

    graph = build_graph(place, date, force_rebuild, memory_gb)
    print(graph)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Builds a graph for a given place and date')
    parser.add_argument('place_id', type=str, help='The place ID or "common" for all common places (see source code)')
    parser.add_argument('target_date', type=str, default="", help='The target date in the format YYYY-MM-DD')
    parser.add_argument('--force-rebuild', action='store_true', help='Force rebuild of graph')
    parser.add_argument('--memory-gb', type=int, default=4,
                        help='The amount of memory to use for the graph build process')

    args = parser.parse_args()

    if args.place_id == "common":
        build_common()
        exit(0)

    build_single(args.target_date, args.place_id, args.force_rebuild, args.memory_gb)


