import datetime
import hashlib
import os
import urllib.request

import bson

from hiveline.routing import gtfs_consistency
from hiveline.routing.servers.routing_server import RoutingServerConfig
from hiveline.routing.util import ensure_directory

type Link = {
    "link": str,
    "date": datetime
}

type PlaceResource = {
    "_id": bson.ObjectId,
    "place-id": bson.ObjectId | str | list[bson.ObjectId | str],
    "osm": list[Link],
    "gtfs": {
        str: list[Link]
    },
    "geofabrik": str,
    "transitfeed": str
}


def build_resources(data_dir: str, place: PlaceResource, target_date: datetime.date) -> RoutingServerConfig:
    """
    Builds the graph for the given place and target date. If the graph already exists, it will not be rebuilt, unless
    force_rebuild=True.
    :param data_dir: The directory where the data should be stored
    :param place: The place resource object
    :param target_date: The target date
    :return: otp_version: The version of OTP used, graph_file: The file name of the graph, osm_source: The resource
             object of the OSM file, gtfs_sources: An array of resource objects of the GTFS files
    """
    osm_resource = __ensure_closest_pbf_downloaded(data_dir, place, target_date)
    gtfs_resources = __ensure_closest_gtfs_downloaded(data_dir, place, target_date)

    print("OSM resource: " + str(osm_resource))
    print("GTFS resources: " + str(gtfs_resources))

    if osm_resource is None or gtfs_resources is None or len(gtfs_resources) == 0:
        raise Exception("No matching OSM or GTFS resource found")

    graph_id = str(place["_id"]) + "-" + target_date.strftime("%Y-%m-%d")

    osm_files = [osm_resource["file"]]
    gtfs_files = [gtfs_resource["file"] for gtfs_resource in gtfs_resources]

    return RoutingServerConfig(graph_id, target_date, data_dir, gtfs_files, osm_files)


def __get_closest_link(link_list: list[Link], target_date: datetime.date, ignore_future: bool = False):
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


def __ensure_data_downloaded(data_dir: str, link_object: Link, file_name_extension: str):
    """
    Ensures that the data file is downloaded.
    :param data_dir: The directory where the data should be stored
    :param link_object: The link object. Must have a "link" key.
    :param file_name_extension: The file name extension
    :return: The file name of the downloaded file
    """
    if file_name_extension[0] != ".":
        file_name_extension = "." + file_name_extension
    if data_dir.endswith("/"):
        data_dir = data_dir[:-1]

    if link_object is None:
        return None

    link = link_object["link"]
    link_hash = hashlib.sha3_256(link.encode()).hexdigest()

    ensure_directory(data_dir)

    target_file_name = data_dir + "/" + link_hash + file_name_extension
    if os.path.isfile(target_file_name):
        return target_file_name, False

    print("Downloading " + link)
    urllib.request.urlretrieve(link, target_file_name)

    return target_file_name, True


def __ensure_closest_pbf_downloaded(data_dir, place, target_date):
    """
    Ensures that the closest OSM file to a target date is downloaded.
    :param data_dir: The directory where the data should be stored
    :param place: The place resource object. Must have an "osm" key.
    :param target_date: The target date
    :return: file: The file name of the downloaded file, source: The source of the file, date: The date of the file
             None if no OSM file was found
    """
    if data_dir.endswith("/"):
        data_dir = data_dir[:-1]

    closest_osm_link = __get_closest_link(place["osm"], target_date)
    if closest_osm_link is None:
        print("No OSM link found")
        return None

    print(closest_osm_link)

    closest_osm_file, _ = __ensure_data_downloaded(data_dir + "/osm", closest_osm_link, ".pbf")
    return {
        "file": closest_osm_file,
        "source": closest_osm_link["link"],
        "date": closest_osm_link["date"]
    }


def __ensure_closest_gtfs_downloaded(data_dir, place, target_date):
    """
    Ensures that the closest GTFS file to a target date is downloaded.
    :param data_dir: The directory where the data should be stored
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

        closest_gtfs_file, downloaded = __ensure_data_downloaded(data_dir + "/gtfs", closest_gtfs_link, ".gtfs.zip")

        if downloaded:
            gtfs_consistency.fix_gtfs(closest_gtfs_file, data_dir + "/gtfs/temp")  # fix inconsistencies

        links.append({
            "file": closest_gtfs_file,
            "source": closest_gtfs_link["link"],
            "date": closest_gtfs_link["date"],
            "provider": provider
        })

    return links
