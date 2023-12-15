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


def iterate_output(stream, debug=False, debug_prefix="[process] "):
    """
    Print the output of a process to the console

    :param stream: the stream to read from
    :param debug: whether to print the output or not
    :param debug_prefix: prefix for the debug output
    :return:
    """
    while True:
        line = stream.readline()
        if not line:
            break
        if debug:
            print(debug_prefix + line.strip())
