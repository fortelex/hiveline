import os
import pathlib


def ensure_directory(path):
    """
    Ensures that the given directory exists. If it does not exist, it will be created.
    :param path: The path to the directory
    :return:
    """
    if not os.path.isdir(path):
        pathlib.Path(path).mkdir(parents=True, exist_ok=True)


def wait_for_line(process, line_to_wait_for):
    """
    Wait for a specific line to appear in the output of a process

    :param process: the process
    :param line_to_wait_for: the line to wait for
    :return:
    """
    while True:
        line = process.stdout.readline()
        if not line:
            raise Exception("Process ended unexpectedly")
        print(line)
        decoded_line = line.strip()
        if line_to_wait_for in decoded_line:
            return
