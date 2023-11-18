import math

from mongo.mongo import get_database
import historical_osmnx
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def find_results_with_osm_nodes(db, sim_id):
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


def get_vc_routes(db, sim_id):
    results = find_results_with_osm_nodes(db, sim_id)

    vc_routes = []

    count = 100

    for result in results:

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
                    "routes": iti_routes,
                    "weight": 1,
                })

                found_car_route = True
                break

            if found_car_route:
                break

        count -= 1
        if count <= 0:
            break

    return vc_routes


def get_usage_set(db, sim_id, total_number_of_people_represented=100000):
    vc_routes = get_vc_routes(db, sim_id)

    total_weight = sum([vc["weight"] for vc in vc_routes])
    weight_factor = total_number_of_people_represented / total_weight

    usage_set = {}

    for vc in vc_routes:
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


def get_congestion_set(db, sim_id, graph, space_for_cars=10, total_number_of_people_represented=1000):
    """
    Get the congestion set for the given simulation id.
    :param db: the database
    :param sim_id: the simulation id
    :param graph: the graph to use for the congestion calculation
    :param space_for_cars: the space reserved for each car in meters * minutes
    :param total_number_of_people_represented: the total number of people represented per minute by the simulation
    :return:
    """
    usage_set = get_usage_set(db, sim_id, total_number_of_people_represented)

    congestion_set = {}

    for (origin, destination), vehicle_count_per_minute in usage_set.items():
        if (origin, destination) in graph.edges:
            edge = graph.edges[(origin, destination, 0)]
        else:
            edge = graph.edges[(destination, origin, 0)]

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

        total_road_capacity = edge["length"] * lanes
        road_usage = vehicle_count_per_minute * space_for_cars / total_road_capacity
        if road_usage == 0:
            road_usage = 1

        speed_factor = 1 / road_usage

        if speed_factor > 1:
            speed_factor = 1

        congestion_set[(origin, destination)] = speed_factor

    return congestion_set


def run_congestion_simulation(sim_id, place_name=None):
    db = get_database()

    graph = historical_osmnx.get_graph(db, sim_id, place_name, True)

    num_people = [10, 100, 1000, 10000]

    for num in num_people:
        congestion_set = get_congestion_set(db, sim_id, graph, total_number_of_people_represented=num)
        print(f"Congestion set for {num} people: {congestion_set}")

        # plot distribution of values in congestion_set

        # convert congestion_set to pandas dataframe
        df = pd.DataFrame.from_dict(congestion_set, orient='index')

        # plot distribution of values in congestion_set
        sns.displot(df)
        plt.title(f"Congestion set for {num} people")
        plt.show()


if __name__ == "__main__":
    run_congestion_simulation("df0d05a9-d8d8-443a-b53b-a513f4baee8e", "Île-de-France, France")
