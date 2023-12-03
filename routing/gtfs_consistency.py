import os.path
import shutil

import pandas as pd
import zipfile

import routing.config as config


def unzip_gtfs(zip_path, unzip_path):
    """
    Unzip a GTFS zip file to a folder
    :param zip_path: The path to the zip file
    :param unzip_path: The path to the folder to unzip to
    :return:
    """
    if os.path.exists(unzip_path):  # delete existing folder
        shutil.rmtree(unzip_path)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(unzip_path)


def zip_gtfs(unzip_path, zip_path):
    """
    Zip a GTFS folder to a zip file
    :param unzip_path: The path to the folder to zip
    :param zip_path: The path to the zip file
    :return:
    """
    if os.path.exists(zip_path):  # delete existing zip file
        os.remove(zip_path)

    # Length of path to remove for correct relative paths
    len_dir_path = len(os.path.dirname(unzip_path))

    # Create a ZipFile object in write mode
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Walk through the directory
        for root, dirs, files in os.walk(unzip_path):
            print(root, dirs, files)
            for file in files:
                # Form the full file path
                file_path = os.path.join(root, file)
                # Add file to the zip file
                zipf.write(file_path, file)


def fix_transfer_stops(gtfs_path):
    """
    Remove transfers that reference stops, routes or trips that don't exist
    :param gtfs_path: The path to the GTFS folder
    :return: True if the GTFS was changed, False if it was not
    """
    stops_file = gtfs_path + "/stops.txt"
    trips_file = gtfs_path + "/trips.txt"
    routes_file = gtfs_path + "/routes.txt"
    transfers_file = gtfs_path + "/transfers.txt"

    if not os.path.exists(transfers_file) or not os.path.exists(stops_file) or not os.path.exists(trips_file) \
            or not os.path.exists(routes_file):
        return False  # invalid, nothing changed

    stops_df = pd.read_csv(stops_file, dtype=str)
    trips_df = pd.read_csv(trips_file, dtype=str)
    routes_df = pd.read_csv(routes_file, dtype=str)
    transfers_df = pd.read_csv(transfers_file, dtype=str)

    num_transfers = len(transfers_df)

    # remove transfers that reference stops that don't exist
    transfers_df = transfers_df[transfers_df["from_stop_id"].isin(stops_df["stop_id"])]
    transfers_df = transfers_df[transfers_df["to_stop_id"].isin(stops_df["stop_id"])]

    # remove transfers that reference trips that don't exist (only if the trip id is not empty)
    if "from_trip_id" in transfers_df.columns:
        transfers_df = transfers_df[
            transfers_df["from_trip_id"].isin(trips_df["trip_id"]) | transfers_df["from_trip_id"].isnull()]
    if "to_trip_id" in transfers_df.columns:
        transfers_df = transfers_df[
            transfers_df["to_trip_id"].isin(trips_df["trip_id"]) | transfers_df["to_trip_id"].isnull()]

    # remove transfers that reference routes that don't exist (only if the route id is not empty)
    if "from_route_id" in transfers_df.columns:
        transfers_df = transfers_df[
            transfers_df["from_route_id"].isin(routes_df["route_id"]) | transfers_df["from_route_id"].isnull()]
    if "to_route_id" in transfers_df.columns:
        transfers_df = transfers_df[
            transfers_df["to_route_id"].isin(routes_df["route_id"]) | transfers_df["to_route_id"].isnull()]

    if len(transfers_df) == num_transfers:
        return False  # nothing changed

    transfers_df.to_csv(transfers_file, index=False)

    return True


def fix_authorities(gtfs_path):
    """
    If a value in the column "agency_url" is missing from the agencies.txt file, add it
    :param gtfs_path: The path to the GTFS folder
    :return: True if the GTFS was changed, False if it was not
    """
    agencies_file = gtfs_path + "/agency.txt"

    if not os.path.exists(agencies_file):
        return False

    agencies_df = pd.read_csv(agencies_file, dtype=str)

    # add agency_url column if it doesn't exist
    if "agency_url" not in agencies_df.columns:
        agencies_df["agency_url"] = "-"

    # add "-" to each row if agency_url is empty string
    agencies_df["agency_url"] = agencies_df["agency_url"].fillna("-")

    agencies_df.to_csv(agencies_file, index=False)

    return True


def fix_gtfs(gtfs_path):
    """
    Fix a GTFS zip file. This will unzip the file, fix it, and re-zip it. It will remove any invalid data. For example
    if there are transfers that reference stops that don't exist, they will be removed.
    :param gtfs_path: The path to the GTFS zip file
    :return:
    """
    temp_dir = config.data_path + "/temp"

    print("Fixing GTFS: " + gtfs_path)

    unzip_gtfs(gtfs_path, temp_dir)

    has_changed = fix_transfer_stops(temp_dir)
    has_changed = fix_authorities(temp_dir) or has_changed

    if not has_changed:
        shutil.rmtree(temp_dir)
        print("GTFS was not changed")
        return False  # nothing changed, skipping re-zip

    zip_gtfs(temp_dir, gtfs_path)

    shutil.rmtree(temp_dir)
    print("GTFS was changed")
