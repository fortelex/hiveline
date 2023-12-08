import os
import re

import osmnx as ox

import config


def __ensure_directory(dir_path):
    """
    Ensure that the directory exists.
    :param dir_path: the directory path
    :return:
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def __get_graph(date_str, place_name, graph_file_location):
    ox.settings.overpass_settings = '[out:json][timeout:90][date:"' + date_str + '"]'

    print("Downloading graph from " + place_name)
    graph = ox.graph_from_place(place_name, network_type='drive')
    print("Saving graph to " + graph_file_location)

    ox.save_graphml(graph, filepath=graph_file_location)
    print("Graph saved.")

    return graph


def get_graph(db, sim_id, place_name=None, undirected=False):
    """
    Get the historical network for the given simulation id.
    :param db: the database
    :param sim_id: the simulation id
    :param place_name: the place name, if None, the place name will be retrieved from the database
    :param undirected: if True, return the undirected version of the graph
    :return:
    """
    simulations = db["simulations"]

    sim = simulations.find_one({"sim-id": sim_id})

    date_str = sim["pivot-date"].isoformat()
    place_id = sim["place-id"]

    if place_name is None:
        place_resources = db["place-resources"]
        resources = place_resources.find_one({"place-id": place_id})
        place_name = resources["place-name"]

    normalized_dataset_name = re.sub(r'[^A-Za-z0-9]+', " ", place_name.lower()).replace(" ", "-") \
                              + "-" + date_str.replace(":", "") \
                              + ("-undirected" if undirected else "")

    __ensure_directory(config.data_path)

    print("Normalized dataset name: " + normalized_dataset_name)

    graph_file_location = config.data_path + "/" + normalized_dataset_name + ".graphml"

    print("Graph file location: " + graph_file_location)

    if os.path.exists(graph_file_location):
        print("Reading graph from " + graph_file_location)
        graph = ox.load_graphml(filepath=graph_file_location)
        return graph

    if undirected:
        print("Undirected graph not found, creating it from the directed graph.")
        di_graph = get_graph(db, sim_id, place_name, undirected=False)
        print("Creating undirected graph.")
        graph = di_graph.to_undirected()
        print("Saving undirected graph to " + graph_file_location)
        ox.save_graphml(graph, filepath=graph_file_location)
        return graph

    return __get_graph(date_str, place_name, graph_file_location)
