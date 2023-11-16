import os.path
import shutil

import pandas as pd
import zipfile


def unzip_gtfs(zip_path, unzip_path):
    """
    Unzip a GTFS zip file to a folder
    :param zip_path: The path to the zip file
    :param unzip_path: The path to the folder to unzip to
    :return:
    """
    if os.path.exists(unzip_path): # delete existing folder
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
    Remove transfers that reference stops that don't exist
    :param gtfs_path: The path to the GTFS folder
    :return:
    """
    stops_file = gtfs_path + "/stops.txt"
    transfers_file = gtfs_path + "/transfers.txt"

    if not os.path.exists(transfers_file) or not os.path.exists(stops_file):
        return False  # nothing changed

    stops_df = pd.read_csv(stops_file)
    transfers_df = pd.read_csv(transfers_file)

    num_transfers = len(transfers_df)
    transfers_df = transfers_df[transfers_df["from_stop_id"].isin(stops_df["stop_id"])]
    transfers_df = transfers_df[transfers_df["to_stop_id"].isin(stops_df["stop_id"])]

    if len(transfers_df) == num_transfers:
        return False  # nothing changed

    transfers_df.to_csv(transfers_file, index=False)

    return True


def fix_gtfs(gtfs_path):
    """
    Fix a GTFS zip file. This will unzip the file, fix it, and re-zip it. It will remove any invalid data. For example
    if there are transfers that reference stops that don't exist, they will be removed.
    :param gtfs_path: The path to the GTFS zip file
    :return:
    """
    temp_dir = "otp/data/temp"

    unzip_gtfs(gtfs_path, temp_dir)

    has_changed = fix_transfer_stops(temp_dir)

    if not has_changed:
        shutil.rmtree(temp_dir)
        return False  # nothing changed, skipping re-zip

    zip_gtfs(temp_dir, gtfs_path)

    shutil.rmtree(temp_dir)
