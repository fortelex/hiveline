import folium
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

import hiveline.vc.vc_extract as vc_extract
from hiveline.mongo.db import get_database
from hiveline.results.modal_shares import Params


class CongestionOptions:
    """
    Options for the congestion analysis.
    """
    max_motorcycle_slowdown = 0.7


def find_results_with_osm_nodes(db, sim_id):
    """
    Find all results that have OSM nodes in their legs
    :param db: the database
    :param sim_id: the simulation id
    :return: a cursor to the results
    """
    route_results = db["route-results"]

    results = route_results.find({
        "sim-id": sim_id,
        "options": {
            "$elemMatch": {
                "itineraries": {
                    "$elemMatch": {
                        "legs": {
                            "$elemMatch": {
                                "osm_nodes": {
                                    "$exists": True
                                }
                            }
                        }
                    }
                }
            }
        }
    })

    return results


def find_all_journeys(db, sim_id):
    """
    Find all route results for a simulation
    :param db: the database
    :param sim_id: the simulation id
    :return: a cursor to the results
    """
    route_results = db["route-results"]

    results = route_results.find({
        "sim-id": sim_id
    })

    return results


def find_matching_route_options(db, sim_id, journeys):
    """
    Find the corresponding route options for the given journeys
    :param db: the database
    :param sim_id: the simulation id
    :param journeys: the journeys
    :return: the route options (same order as journeys)
    """
    route_options = db["route-options"]

    route_options = list(route_options.find({"sim-id": sim_id}))

    route_options = {option["vc-id"]: option for option in route_options}

    return [route_options[journey["vc-id"]] for journey in journeys]


def get_car_routes(journeys, mask=None):
    """
    Get all car routes from a set of journeys. Car routes are lists of OSM nodes.
    :param journeys: the journeys
    :param mask: (optional) a mask to filter out journeys
    :return: a list of objects with the following fields:
        - vc-id: the virtual commuter id
        - option-id: the route option id
        - routes: a list of car routes
        - weight: the weight of the route option
    """
    vc_routes = []

    has_mask = mask is not None

    for i in range(len(journeys)):
        result = journeys[i]

        if has_mask and not mask[i]:
            continue

        for option in result["options"]:
            if option is None:
                continue

            found_car_route = False

            for itinerary in option["itineraries"]:
                iti_routes = []

                for leg in itinerary["legs"]:
                    if "osm_nodes" in leg:
                        iti_routes.append(leg["osm_nodes"])

                if len(iti_routes) == 0:
                    continue

                vc_routes.append({
                    "vc-id": result["vc-id"],
                    "option-id": option["route-option-id"],
                    "routes": iti_routes,
                    "weight": 1,
                })

                found_car_route = True
                break

            if found_car_route:
                break

    return vc_routes


def get_usage_set(journeys, mask=None, vehicles_per_journey=1.0):
    """
    Get the usage set of a set of journeys. The usage set is a dictionary of edges and their usage.
    :param journeys: a list of journeys
    :param mask: (optional) a mask to filter out journeys
    :param vehicles_per_journey: the number of vehicles per journey
    :return: a dictionary of edges and their usage. keys are tuples of OSM nodes, values are floats.
    """
    car_routes = get_car_routes(journeys, mask)

    total_weight = sum([vc["weight"] for vc in car_routes])

    total_num_vehicles = len(car_routes) * vehicles_per_journey

    weight_factor = total_num_vehicles / total_weight if total_weight > 0 else 0

    usage_set = {}

    for vc in car_routes:
        routes = vc["routes"]
        weight = vc["weight"]

        for route in routes:
            for (origin, destination) in zip(route[:-1], route[1:]):
                key = (origin, destination)
                if origin > destination:
                    key = (destination, origin)

                if key not in usage_set:
                    usage_set[key] = 0
                usage_set[key] += weight * weight_factor

    return usage_set


def get_edges(db, sim_id, journeys):
    """
    Get the edges for the given simulation id.
    :param db: the database
    :param sim_id: the simulation id
    :param journeys: the journeys to consider
    :return: a dictionary of edges and their metadata. keys are tuples of OSM nodes, values are dictionaries.
    """
    usage_set = get_usage_set(journeys, mask=None, vehicles_per_journey=0)

    sim = db["simulations"].find_one({"sim-id": sim_id})

    pivot_time = sim["pivot-date"]
    pivot_time.replace(tzinfo=None)
    date_str = pivot_time.isoformat()

    edges_to_download = []

    for (origin, destination), _ in usage_set.items():
        edges_to_download.append((origin, destination, date_str))

    # split into chunks of 1000
    chunks = [edges_to_download[x:x + 1000] for x in range(0, len(edges_to_download), 1000)]

    edges = {}
    edge_coll = db["street-edge-data"]

    for chunk in chunks:
        edge_ids = [str(origin) + "-" + str(destination) + "-" + date_str for (origin, destination, date_str) in chunk]

        result = list(edge_coll.find({"edge-id": {"$in": edge_ids}}))

        edge_id_set = {edge["edge-id"]: edge for edge in result}

        edge_key_set = {(chunk[i][0], chunk[i][1]): edge_id_set[edge_ids[i]] for i in range(len(chunk))}

        edges.update(edge_key_set)

    return edges


def get_nodes(db, sim_id, edges):
    """
    Get the nodes for the given simulation id.
    :param db: the database
    :param sim_id: the simulation id
    :param journeys: the journeys to consider
    :return: a dictionary of nodes and their metadata. keys are OSM node ids, values are dictionaries.
    """
    sim = db["simulations"].find_one({"sim-id": sim_id})

    pivot_time = sim["pivot-date"]
    pivot_time.replace(tzinfo=None)
    date_str = pivot_time.isoformat()

    node_set = set()

    for (origin, destination) in edges.keys():
        node_set.add(origin)
        node_set.add(destination)

    node_list = list(node_set)

    print("Downloading {} nodes".format(len(node_list)))

    chunks = [node_list[x:x + 1000] for x in range(0, len(node_list), 1000)]

    nodes = {}

    node_coll = db["street-node-data"]

    for chunk in chunks:
        node_ids = [str(node) + "-" + date_str for node in chunk]

        result = list(node_coll.find({"node-id": {"$in": node_ids}}))

        node_id_set = {node["node-id"]: node for node in result}

        node_key_set = {chunk[i]: node_id_set[node_ids[i]] for i in range(len(chunk))}

        nodes.update(node_key_set)

    print("Downloaded {} nodes".format(len(nodes)))

    return nodes


def get_congestion_set(journeys, edges, mask=None, vehicles_per_journey=1.0):
    """
    Get the congestion set for the given simulation id.
    :param journeys: the journeys to consider
    :param edges: metadata about the edges
    :param mask: the mask to apply to the journeys. If None, all journeys are considered
    :param vehicles_per_journey: how many vehicles each journey represents
    :return: a dictionary of edges and their congestion. keys are tuples of OSM nodes, values are floats.
    The values are between 0 and 1 and represent the speed factor to apply to the edge.
    """
    usage_set = get_usage_set(journeys, mask, vehicles_per_journey)

    congestion_set = {}

    for (origin, destination), vehicle_count_per_minute in usage_set.items():
        if origin > destination:
            raise ValueError("Origin is greater than destination")

        edge = edges[(origin, destination)]["edge"]

        lanes = 2

        if "lanes" in edge:
            lanes_str = edge["lanes"]

            if type(lanes_str) is list:
                lanes_str = lanes_str[0]

            try:
                lanes = int(lanes_str)
            except ValueError or TypeError as e:
                print(e)
                pass

            if lanes == 0:
                lanes = 2

        total_road_capacity = lanes
        road_usage = vehicle_count_per_minute / total_road_capacity
        if road_usage == 0:
            road_usage = 1

        speed_factor = 1 / road_usage

        if speed_factor > 1:
            speed_factor = 1

        congestion_set[(origin, destination)] = speed_factor

    return congestion_set


def get_leg_delay(leg, traveller, edges, congestion_set, options=None):
    """
    Get the delay for a leg.
    :param leg: the leg
    :param traveller: the traveller that uses the leg
    :param edges: the set of edges
    :param congestion_set: the congestion set (from get_congestion_set)
    :param options: congestion options
    :return: the delay in seconds
    """
    if options is None:
        options = CongestionOptions()

    has_moto = vc_extract.has_motorcycle(traveller)

    osm_nodes = leg["osm_nodes"]

    edge_keys = [
        (osm_nodes[i], osm_nodes[i + 1]) if osm_nodes[i] < osm_nodes[i + 1] else (osm_nodes[i + 1], osm_nodes[i]) for i
        in range(len(osm_nodes) - 1)]

    for (origin, destination) in edge_keys:
        if origin > destination:
            raise ValueError("Origin is greater than destination")

    edges = [edges[key] for key in edge_keys]

    # if a key is not in congestion_set, no active car visited that edge, so speed factor is 1
    speed_factors = [congestion_set[key] if key in congestion_set else 1 for key in edge_keys]

    # total speed factor is the weighted average of speed factors for each edge (weighted by edge length)
    total_length = sum([edge["edge"]["length"] for edge in edges])
    total_speed_factor = sum([speed_factor * edge["edge"]["length"] for (speed_factor, edge) in
                              zip(speed_factors, edges)]) / total_length

    if has_moto and total_speed_factor > options.max_motorcycle_slowdown:
        total_speed_factor = options.max_motorcycle_slowdown

    planned_duration = leg["endTime"] - leg["startTime"]

    actual_duration = planned_duration / total_speed_factor

    return actual_duration - planned_duration


def get_delay_set_from_congestion(congestion_set, journeys, route_options, edges, options=None):
    """
    Get the delay set for the given congestion set.
    :param congestion_set: The congestion set to use
    :param journeys: The journeys to consider
    :param route_options: The corresponding route options (must be in the same order as the journeys)
    :param edges: Metadata about the edges (street-edge-data)
    :param options: Congestion options
    :return: A dictionary mapping route-option-ids to the delay for that route option
    """
    if options is None:
        options = CongestionOptions()

    congestion_delays = {}

    for (result, route_option) in zip(journeys, route_options):
        traveller = route_option["traveller"]

        for option in result["options"]:
            if option is None:
                continue

            found_car_route = False

            for (index, itinerary) in enumerate(option["itineraries"]):
                itinerary_delay = 0

                for leg in itinerary["legs"]:
                    if "osm_nodes" not in leg:
                        continue
                    found_car_route = True

                    leg_delay = get_leg_delay(leg, traveller, edges, congestion_set, options)
                    itinerary_delay += leg_delay

                if not found_car_route:
                    continue

                congestion_key = option["route-option-id"]
                congestion_delays[congestion_key] = itinerary_delay

                break
            if found_car_route:
                break

    return congestion_delays


def get_delay_set(journeys, route_options, edges, mask=None, vehicles_per_journey=1.0, options=None):
    """
    Get the delay set for the given journeys
    :param journeys: The journeys to consider
    :param route_options: The corresponding route options (must be in the same order as the journeys)
    :param edges: Metadata about the edges (street-edge-data)
    :param mask: The mask to apply to the journeys. If None, all journeys are considered
    :param vehicles_per_journey: How many vehicles each journey represents
    :param options: Congestion options
    :return: A dictionary mapping route-option-ids to the delay for that route option
    """
    if options is None:
        options = CongestionOptions()

    congestion_set = get_congestion_set(journeys, edges, mask, vehicles_per_journey)
    return get_delay_set_from_congestion(congestion_set, journeys, route_options, edges, options)


def plot_delays_for_factors(sim_id, vehicle_factors, total_citizens=1000.0):
    """
    Plot the delay for different vehicle factors.
    :param sim_id: the simulation id
    :param vehicle_factors: the vehicle factors to consider
    :param total_citizens: the total number of citizens in the simulation
    :return:
    """
    db = get_database()

    # count route-results
    num_results = db["route-results"].count_documents({"sim-id": sim_id})

    vehicles_per_journey = total_citizens / num_results
    print(f"Vehicles per journey: {vehicles_per_journey}")

    vehicle_factors = [vehicles_per_journey * factor for factor in vehicle_factors]

    journeys = list(find_results_with_osm_nodes(db, sim_id))
    route_options = find_matching_route_options(db, sim_id, journeys)
    edges = get_edges(db, sim_id, journeys)

    for vehicles_per_journey in vehicle_factors:
        delay_set = get_delay_set(journeys, route_options, edges, mask=None, vehicles_per_journey=vehicles_per_journey)
        print(f"Congestion set for {vehicles_per_journey} vehicles per journey")

        # plot distribution of values in delay_set

        # convert congestion_set to pandas dataframe
        df = pd.DataFrame.from_dict(delay_set, orient='index')

        # plot distribution of values in congestion_set
        sns.displot(df)
        plt.title(f"Congestion set for {vehicles_per_journey} vehicles per journey")
        plt.show()


# def run_congestion_simulation(db, sim_id, params: Params):
#     """
#     Run the decision algorithm with congestion simulation
#     :param db: the database
#     :param sim_id: the simulation id
#     :param params: the simulation parameters
#     :return: a dict with the results and sturctures used
#     - modal_share: the modal share if the last iteration
#     - congestion_set: the congestion set of the last iteration
#     - iterations: the number of iterations
#     - journeys: the journeys analyzed
#     - edges: the edges used by the journeys
#     - mask: the mask of journeys that use a car in the last iteration
#     """
#     # count route-results
#     num_results = db["route-results"].count_documents({"sim-id": sim_id})
#
#     vehicles_per_journey = params.vehicle_factor * params.num_citizens / num_results
#     print(f"Vehicles per journey: {vehicles_per_journey}")
#
#     journeys = list(congestion.find_all_journeys(db, sim_id))
#     route_options = congestion.find_matching_route_options(db, sim_id, journeys)
#     edges = congestion.get_edges(db, sim_id, journeys)
#
#     # start off with half of the vcs on the road
#
#     mask = [random.random() < params.vcs_car_usage_start for _ in range(len(journeys))]
#     last_modal_share = None
#     last_congestion_set = None
#
#     i = -1
#
#     while True:
#         i += 1
#
#         congestion_set = get_congestion_set(journeys, edges, mask, vehicles_per_journey)
#         delay_set = get_delay_set_from_congestion(congestion_set, journeys, route_options, edges,
#                                                   params.congestion_options)
#
#         stats, next_mask = get_stats_from_route_options(route_options, mask, delay_set)
#
#         modal_share = get_transit_modal_share(stats)
#
#         print(f"Iteration {i} - transit modal share: {modal_share * 100}%")
#
#         if last_modal_share is None:
#             last_modal_share = modal_share
#             continue
#
#         diff = abs(modal_share - last_modal_share)
#
#         last_modal_share = modal_share
#         last_congestion_set = congestion_set
#
#         if diff < 0.001 or i > 100:
#             break
#
#         # update mask
#         for j in range(len(mask)):
#             if random.random() < params.mix_factor:
#                 mask[j] = next_mask[j]
#
#     return {
#         "modal_share": modal_share,
#         "congestion_set": last_congestion_set,
#         "iterations": i,
#         "journeys": journeys,
#         "edges": edges,
#         "mask": mask
#     }


def plot_congestion_for_set(f_map, congestion_set, nodes):
    # Define a color scale
    # linear = cm.LinearColormap(colors=plt.cm.inferno.colors, index=[0, 1], vmin=0, vmax=1)

    inferno = plt.cm.get_cmap('inferno')

    for (origin, destination), speed_factor in congestion_set.items():
        origin_node = nodes[origin]["node"]
        destination_node = nodes[destination]["node"]

        origin_point = (origin_node["y"], origin_node["x"])
        destination_point = (destination_node["y"], destination_node["x"])

        col = inferno(1 - speed_factor)
        col_hex = matplotlib.colors.rgb2hex(col)
        folium.PolyLine([origin_point, destination_point], color=col_hex,
                        opacity=1 - speed_factor).add_to(f_map)

    return f_map


def plot_congestion_for_sim(f_map, sim_id, params=None):
    db = get_database()

    if params is None:
        params = Params()

    params.vehicle_factor = 0.001  # high vehicle factor to see congestion

    db = get_database()

    num_results = db["route-results"].count_documents({"sim-id": sim_id})

    vehicles_per_journey = params.vehicle_factor * params.num_citizens / num_results
    print(f"Vehicles per journey: {vehicles_per_journey}")

    journeys = list(find_all_journeys(db, sim_id))
    route_options = find_matching_route_options(db, sim_id, journeys)

    mask = [vc_extract.would_use_motorized_vehicle(route_option["traveller"]) for route_option in route_options]

    edges = get_edges(db, sim_id, journeys)

    congestion_set = get_congestion_set(journeys, edges, mask, vehicles_per_journey)
    # data = run_congestion_simulation(db, sim_id, params)

    nodes = get_nodes(db, sim_id, edges)

    return plot_congestion_for_set(f_map, congestion_set, nodes)


if __name__ == "__main__":
    num_citizens = 2000000
    plot_delays_for_factors("735a3098-8a19-4252-9ca8-9372891e90b3", [0.0001, 0.001, 0.01], total_citizens=num_citizens)
