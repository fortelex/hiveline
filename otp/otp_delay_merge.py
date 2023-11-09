from os import listdir
from os.path import isfile, join

import pandas as pd


# merge multiple delay files into one
def merge_files(directory, output_file):
    directory = directory.rstrip("/") + "/"

    data_frames = []

    delay_files = [f for f in listdir(directory) if isfile(join(directory, f))]
    for file in delay_files:
        df = pd.read_csv(directory + file, sep=",")

        normalized_name = file.rstrip(".csv").lower()

        df["agency"] = normalized_name

        data_frames.append(df)

    df = pd.concat(data_frames)

    df.to_csv(output_file, sep=",", index=False)


merge_files("./delay_statistics/", "delay_statistics.csv")