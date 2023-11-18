import math
import random

import folium
import numpy as np
from matplotlib import pyplot as plt

from mongo.mongo import get_database
import vc_extract
import congestion

import branca.colormap as cm

transit_modes = ["bus", "rail", "tram", "subway"]


class Params:
    """
    Simulation parameters for congestion and modal share analysis
    """
    num_citizens = 2000000
    vehicle_factor = 0.00007
    vcs_car_usage_start = 0.5
    mix_factor = 0.1
    max_iterations = 100

    congestion_options = congestion.CongestionOptions()


def get_modal_share(route_options, mask=None, delay_set=None):
    """
    Get the modal share for a set of route options
    :param route_options: the route options
    :param mask: (optional) a mask to apply to the route options
    :param delay_set: (optional) a set of route-option-ids to delay (dictionary with route option id as key and delay in seconds as value)
    :return: a dictionary with the modal share
    """
    total_car_meters = 0
    total_transit_meters = 0

    total_car_passengers = 0
    total_transit_passengers = 0
    total_walkers = 0

    car_owners_choosing_cars = 0
    car_owners_choosing_transit = 0
    car_owners_choosing_walk = 0

    i = -1

    out_mask = None if mask is None else [True] * len(mask)  # get mask with delay set

    # get mask with delay set
    for result in route_options:
        i += 1

        if out_mask is not None:
            out_mask[i] = False

        options = result["options"]

        has_car = vc_extract.has_motor_vehicle(result["traveller"])  # does the vc own a car?

        # choose the fastest option
        fastest_option = None
        fastest_option_duration = 0

        for option in options:
            if option is None:
                continue

            option_duration = option["route-duration"]
            option_id = option["route-option-id"]
            option_delay = 0
            if delay_set is not None and option_id in delay_set:
                option_delay = delay_set[option_id]

            option_duration += option_delay

            if fastest_option is None:
                fastest_option = option
                fastest_option_duration = option_duration
                continue

            if option_duration < fastest_option_duration:
                fastest_option = option
                fastest_option_duration = option_duration

        if fastest_option is None:
            continue

        legs = fastest_option["modes"]

        is_car = False  # is the fastest mode a car trip?
        is_transit = False  # is the fastest mode a transit trip?
        length = 0  # total length of motorized travel in meters

        for leg in legs:
            mode = leg["mode"]

            if mode == "car":
                length += leg["distance"]
                is_car = True
                continue

            if mode in transit_modes:
                length += leg["distance"]
                is_transit = True
                continue

            if mode == "bicycle":
                continue

            if mode == "walk":
                continue

            print(f"Unknown mode: {mode}")

        if out_mask is not None:
            out_mask[i] = is_car  # if the fastest mode is a car, use a car

        if is_car and is_transit:
            print("Mixed mode trip. Skipping.")
            continue

        if is_car and has_car:
            car_owners_choosing_cars += 1

        if is_transit and has_car:
            car_owners_choosing_transit += 1

        if not is_car and not is_transit and has_car:
            car_owners_choosing_walk += 1

        if is_car:
            total_car_meters += length
            total_car_passengers += 1

        if is_transit:
            total_transit_meters += length
            total_transit_passengers += 1

        if not is_car and not is_transit:
            total_walkers += 1

    return {
        "total_car_meters": total_car_meters,
        "total_transit_meters": total_transit_meters,
        "total_car_passengers": total_car_passengers,
        "total_transit_passengers": total_transit_passengers,
        "total_walkers": total_walkers,
        "car_owners_choosing_cars": car_owners_choosing_cars,
        "car_owners_choosing_transit": car_owners_choosing_transit,
        "car_owners_choosing_walk": car_owners_choosing_walk,
        "mask": out_mask
    }


def get_transit_modal_share(stats):
    """
    Get the transit modal share from the stats
    :param stats: the stats from get_modal_share
    :return: the transit modal share
    """
    total_car_meters = stats["total_car_meters"]
    total_transit_meters = stats["total_transit_meters"]

    total_car_passengers = stats["total_car_passengers"]
    total_transit_passengers = stats["total_transit_passengers"]

    car_passenger_meters = total_car_meters * total_car_passengers
    transit_passenger_meters = total_transit_meters * total_transit_passengers

    total_passenger_meters = car_passenger_meters + transit_passenger_meters

    return transit_passenger_meters / total_passenger_meters


def run_decisions(db, sim_id):
    """
    Run decision algorithm without congestion simulation
    :param db: the database
    :param sim_id: the simulation id
    :return:
    """
    route_options = db["route-options"]

    results = route_options.find({"sim-id": sim_id})

    stats = get_modal_share(results)

    print(stats)

    transit_modal_share = get_transit_modal_share(stats)

    print(f"Transit modal share: {transit_modal_share * 100}%")


def run_congestion_simulation(db, sim_id, params: Params):
    """
    Run the decision algorithm with congestion simulation
    :param db: the database
    :param sim_id: the simulation id
    :param params: the simulation parameters
    :return: a dict with the results and sturctures used
    - modal_share: the modal share if the last iteration
    - congestion_set: the congestion set of the last iteration
    - iterations: the number of iterations
    - journeys: the journeys analyzed
    - edges: the edges used by the journeys
    - mask: the mask of journeys that use a car in the last iteration
    """
    # count route-results
    num_results = db["route-results"].count_documents({"sim-id": sim_id})

    vehicles_per_journey = params.vehicle_factor * params.num_citizens / num_results
    print(f"Vehicles per journey: {vehicles_per_journey}")

    journeys = list(congestion.find_all_journeys(db, sim_id))
    route_options = congestion.find_matching_route_options(db, sim_id, journeys)
    edges = congestion.get_edges(db, sim_id, journeys)

    # start off with half of the vcs on the road

    mask = [random.random() < params.vcs_car_usage_start for _ in range(len(journeys))]
    last_modal_share = None
    last_congestion_set = None

    i = -1

    while True:
        i += 1

        congestion_set = congestion.get_congestion_set(journeys, edges, mask, vehicles_per_journey)
        delay_set = congestion.get_delay_set_from_congestion(congestion_set, journeys, route_options, edges,
                                                             params.congestion_options)

        stats = get_modal_share(route_options, mask, delay_set)
        next_mask = stats["mask"]

        modal_share = get_transit_modal_share(stats)

        print(f"Iteration {i} - transit modal share: {modal_share * 100}%")

        if last_modal_share is None:
            last_modal_share = modal_share
            continue

        diff = abs(modal_share - last_modal_share)

        last_modal_share = modal_share
        last_congestion_set = congestion_set

        if diff < 0.001 or i > 100:
            break

        # update mask
        for j in range(len(mask)):
            if random.random() < params.mix_factor:
                mask[j] = next_mask[j]

    return {
        "modal_share": modal_share,
        "congestion_set": last_congestion_set,
        "iterations": i,
        "journeys": journeys,
        "edges": edges,
        "mask": mask
    }


def get_congestion_sim_modal_share(db, sim_id, params: Params):
    """
    Run the decision algorithm with congestion simulation
    :param db: the database
    :param sim_id: the simulation id
    :param params: the simulation parameters
    :return: the modal share
    """

    data = run_congestion_simulation(db, sim_id, params)
    modal_share = data["modal_share"]

    return modal_share


def plot_vehicle_factors(sim_id):
    """
    Plot the vehicle factors vs the transit modal share
    :param sim_id: the simulation id
    :return:
    """
    plot_factors(sim_id, "vehicle_factor", 0.000002 * np.arange(1, 100, 10))


def plot_mix_factors(sim_id):
    """
    Plot the mix factors vs the transit modal share
    :param sim_id: the simulation id
    :return:
    """
    plot_factors(sim_id, "mix_factor", np.arange(0.1, 1, 0.1))


def plot_vcs_car_usage_start(sim_id):
    """
    Plot the vcs car usage start factors vs the transit modal share
    :param sim_id: the simulation id
    :return:
    """
    plot_factors(sim_id, "vcs_car_usage_start", np.arange(0.1, 1, 0.1))


def plot_factors(sim_id, factor_key, factors):
    """
    Plot the given factors vs the transit modal share
    :param sim_id: the simulation id
    :param factor_key: the factor key (field name in Params)
    :param factors: the factors to plot
    :return:
    """
    db = get_database()
    params = Params()

    modal_shares = []

    for factor in factors:
        setattr(params, factor_key, factor)

        modal_share = get_congestion_sim_modal_share(db, sim_id, params)

        modal_shares.append(modal_share)

    # plot factor vs modal share
    plt.plot(factors, modal_shares)
    plt.xlabel(factor_key)
    plt.ylabel("Transit modal share")
    plt.show()


def plot_congestion_for_set(congestion_set, nodes):
    some_node = next(iter(nodes.values()))["node"]

    f_map = folium.Map(location=[some_node["y"], some_node["x"]], zoom_start=11, tiles='CartoDB dark_matter')

    # Define a color scale
    linear = cm.LinearColormap(colors=['#00ccff', '#BBD460'], index=[0, 1], vmin=0, vmax=1)

    for (origin, destination), speed_factor in congestion_set.items():
        origin_node = nodes[origin]["node"]
        destination_node = nodes[destination]["node"]

        origin_point = (origin_node["y"], origin_node["x"])
        destination_point = (destination_node["y"], destination_node["x"])

        folium.PolyLine([origin_point, destination_point], color=linear(1 - speed_factor),
                        opacity=1 - speed_factor).add_to(f_map)

    linear.add_to(f_map)

    return f_map


def plot_congestion_for_sim(sim_id):
    db = get_database()
    params = Params()

    params.vehicle_factor = 0.001  # high vehicle factor to see congestion

    data = run_congestion_simulation(db, sim_id, params)
    congestion_set = data["congestion_set"]
    edges = data["edges"]

    nodes = congestion.get_nodes(db, sim_id, edges)

    f_map = plot_congestion_for_set(congestion_set, nodes)

    f_map.save("congestion.html")


if __name__ == "__main__":
    # plot_vehicle_factors("735a3098-8a19-4252-9ca8-9372891e90b3")
    plot_congestion_for_sim("735a3098-8a19-4252-9ca8-9372891e90b3")
