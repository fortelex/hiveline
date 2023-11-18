import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from mongo.mongo import get_database


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


def get_vc_routes(journeys, mask=None):
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
    vc_routes = get_vc_routes(journeys, mask)

    total_weight = sum([vc["weight"] for vc in vc_routes])

    total_num_vehicles = len(journeys) * vehicles_per_journey

    if mask is not None:
        total_num_vehicles = sum(mask) * vehicles_per_journey

    weight_factor = total_num_vehicles / total_weight

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


def get_edges(db, sim_id, journeys):
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


def get_congestion_set(journeys, edges, mask=None, vehicles_per_journey=1.0):
    """
    Get the congestion set for the given simulation id.
    :param journeys: the journeys to consider
    :param edges: metadata about the edges
    :param mask: the mask to apply to the journeys. If None, all journeys are considered
    :param vehicles_per_journey: how many vehicles each journey represents
    :return:
    """
    usage_set = get_usage_set(journeys, mask, vehicles_per_journey)

    congestion_set = {}

    for (origin, destination), vehicle_count_per_minute in usage_set.items():
        if (origin, destination) in edges:
            edge = edges[(origin, destination)]["edge"]
        else:
            edge = edges[(destination, origin)]["edge"]

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
        road_usage = vehicle_count_per_minute / total_road_capacity
        if road_usage == 0:
            road_usage = 1

        speed_factor = 1 / road_usage

        if speed_factor > 1:
            speed_factor = 1

        congestion_set[(origin, destination)] = speed_factor

    return congestion_set


def get_leg_delay(leg, edges, congestion_set):
    osm_nodes = leg["osm_nodes"]

    edge_keys = [
        (osm_nodes[i], osm_nodes[i + 1]) if osm_nodes[i] < osm_nodes[i + 1] else (osm_nodes[i + 1], osm_nodes[i]) for i
        in range(len(osm_nodes) - 1)]

    edges = [edges[key] for key in edge_keys]
    speed_factors = [congestion_set[key] for key in edge_keys]

    # total speed factor is the weighted average of speed factors for each edge (weighted by edge length)
    total_length = sum([edge["edge"]["length"] for edge in edges])
    total_speed_factor = sum([speed_factor * edge["edge"]["length"] for (speed_factor, edge) in
                              zip(speed_factors, edges)]) / total_length

    planned_duration = leg["endTime"] - leg["startTime"]

    actual_duration = planned_duration / total_speed_factor

    return actual_duration - planned_duration


def get_delay_set(journeys, edges, mask=None, vehicles_per_journey=1.0):
    congestion_set = get_congestion_set(journeys, edges, mask, vehicles_per_journey)

    congestion_delays = {}

    for result in journeys:
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

                    leg_delay = get_leg_delay(leg, edges, congestion_set)
                    itinerary_delay += leg_delay

                if not found_car_route:
                    continue

                congestion_key = (option["route-option-id"], index)
                congestion_delays[congestion_key] = itinerary_delay / 60  # minutes

                break
            if found_car_route:
                break

    return congestion_delays


def run_congestion_simulation(sim_id, total_citizens=1000.0):
    db = get_database()

    # count route-results
    num_results = db["route-results"].count_documents({"sim-id": sim_id})

    vehicles_per_journey = total_citizens / num_results
    print(f"Vehicles per journey: {vehicles_per_journey}")

    vehicle_factors = [0.0001, 0.001, 0.01]
    vehicle_factors = [vehicles_per_journey * factor for factor in vehicle_factors]

    journeys = list(find_results_with_osm_nodes(db, sim_id))
    edges = get_edges(db, sim_id, journeys)

    for vehicles_per_journey in vehicle_factors:
        delay_set = get_delay_set(journeys, edges, mask=None, vehicles_per_journey=vehicles_per_journey)
        print(f"Congestion set for {vehicles_per_journey} vehicles per journey")

        # plot distribution of values in delay_set

        # convert congestion_set to pandas dataframe
        df = pd.DataFrame.from_dict(delay_set, orient='index')

        # plot distribution of values in congestion_set
        sns.displot(df)
        plt.title(f"Congestion set for {vehicles_per_journey} vehicles per journey")
        plt.show()


if __name__ == "__main__":
    num_citizens = 2000000
    run_congestion_simulation("735a3098-8a19-4252-9ca8-9372891e90b3", total_citizens=num_citizens)
