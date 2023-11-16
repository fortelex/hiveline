import math
from os import listdir
from os.path import isfile, join

import pandas as pd
import pymongo.errors

from mongo import mongo


def read_and_upload_statistics(directory):
    db = mongo.get_database()
    coll = db["delay_statistics"]

    directory = directory.rstrip("/") + "/"

    delay_files = [f for f in listdir(directory) if isfile(join(directory, f))]
    for file in delay_files:
        df = pd.read_csv(directory + file, sep=",")

        bins = []
        substituted_percent = 0
        cancelled_percent = 0

        for index, row in df.iterrows():
            label = row["label"]
            weight = float(str(row["percent"]).rstrip("%"))

            if math.isnan(weight):
                weight = 0

            if label == "substituted":
                substituted_percent = weight
                continue
            if label == "cancelled":
                cancelled_percent = weight
                continue

            bin_start = int(label.rstrip("–"))
            bins += [(bin_start, weight)]

        bins = sorted(bins, key=lambda x: x[0])

        starts = [x[0] for x in bins]
        weights = [x[1] for x in bins]

        # normalize weights
        weight_sum = sum(weights)
        weights = [x / weight_sum for x in weights]

        normalized_name = file.rstrip(".csv").lower()

        doc = {
            "name": normalized_name,
            "starts": starts,
            "weights": weights,
            "substituted_percent": substituted_percent,
            "cancelled_percent": cancelled_percent
        }

        try:
            coll.insert_one(dict(doc))
        except pymongo.errors.DuplicateKeyError:
            coll.replace_one({"name": normalized_name}, doc)


read_and_upload_statistics("./otp/delay_statistics/")
