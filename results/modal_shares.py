import datetime
import os
import random
import time
import uuid

import folium
import matplotlib.colors
import numpy as np
from matplotlib import pyplot as plt
from selenium import webdriver

from mongo.mongo import get_database
import vc_extract
import congestion

rail_modes = ["rail", "tram", "subway"]


class Params:
    """
    Simulation parameters for congestion and modal share analysis
    """
    num_citizens = 2000000
    vehicle_factor = 0.00007
    vcs_car_usage_start = 0.5
    mix_factor = 0.1
    max_iterations = 100
    car_ownership_override = 0  # probability that a vc will own a car even though they don't have one. all of these would use it as well.
    car_usage_override = 0  # probability that a car owner would choose a car even though there is no parking

    congestion_options = congestion.CongestionOptions()


def __option_has_car(option):
    """
    Check if a route option has a car leg
    :param option: the route option
    :return: True if the route option has a car leg, False otherwise
    """

    for leg in option["modes"]:
        if leg["mode"] == "car":
            return True

    return False


def get_modal_share(route_options, mask=None, delay_set=None, out_selection=None, params=None):
    """
    Get the modal share for a set of route options
    :param route_options: the route options
    :param mask: (optional) a mask to apply to the route options
    :param delay_set: (optional) a set of route-option-ids to delay (dictionary with route option id as key and delay in seconds as value)
    :param out_selection: (optional) a list to store the selected route options (route-option-id list)
    :param params: (optional) the simulation parameters
    :return: a dictionary with the modal share
    """
    if params is None:
        params = Params()

    total_car_meters = 0
    total_rail_meters = 0
    total_bus_meters = 0
    total_walk_meters = 0

    total_car_passengers = 0
    total_rail_passengers = 0
    total_bus_passengers = 0
    total_walkers = 0

    car_owners_choosing_cars = 0
    car_owners_choosing_transit = 0
    car_owners_choosing_walk = 0

    i = -1

    out_mask = None if mask is None else [True] * len(mask)  # get mask with delay set

    would_use_car_count = 0
    wouldnt_use_car_count = 0

    # get mask with delay set
    for result in route_options:
        i += 1

        if out_mask is not None:
            out_mask[i] = False

        options = result["options"]

        would_use_car = vc_extract.would_use_motorized_vehicle(
            result["traveller"])  # would the vc use a motorized vehicle?

        has_car = vc_extract.has_motor_vehicle(result["traveller"])  # does the vc have a motorized vehicle?

        if not has_car and random.random() < params.car_ownership_override:
            has_car = True
            would_use_car = True

        if not would_use_car and has_car and random.random() < params.car_usage_override:
            would_use_car = True

        if would_use_car:
            would_use_car_count += 1
        else:
            wouldnt_use_car_count += 1

        # choose the fastest option
        fastest_option = None
        fastest_option_duration = 0

        for option in options:
            if option is None:
                continue

            if not would_use_car and __option_has_car(option):
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

        for leg in legs:
            mode = leg["mode"]

            if mode == "car":
                is_car = True
                total_car_meters += leg["distance"]
                total_car_passengers += 1
                continue

            if mode in rail_modes:
                is_transit = True
                total_rail_meters += leg["distance"]
                total_rail_passengers += 1
                continue

            if mode == "bus":
                is_transit = True
                total_bus_meters += leg["distance"]
                total_bus_passengers += 1
                continue

            if mode == "bicycle":
                continue

            if mode == "walk":
                total_walk_meters += leg["distance"]
                total_walkers += 1
                continue

            print(f"Unknown mode: {mode}")

        if out_mask is not None:
            out_mask[i] = is_car  # if the fastest mode is a car, use a car

        if out_selection is not None:
            out_selection[i] = fastest_option["route-option-id"]

        if is_car and is_transit:
            print("Mixed mode trip. Skipping.")
            continue

        if is_car and would_use_car:
            car_owners_choosing_cars += 1

        if is_transit and would_use_car:
            car_owners_choosing_transit += 1

        if not is_car and not is_transit and would_use_car:
            car_owners_choosing_walk += 1

    return {
               "total_car_meters": total_car_meters,
               "total_rail_meters": total_rail_meters,
               "total_bus_meters": total_bus_meters,
               "total_walk_meters": total_walk_meters,
               "total_car_passengers": total_car_passengers,
               "total_rail_passengers": total_rail_passengers,
               "total_bus_passengers": total_bus_passengers,
               "total_walkers": total_walkers,
               "car_owners_choosing_cars": car_owners_choosing_cars,
               "car_owners_choosing_transit": car_owners_choosing_transit,
               "car_owners_choosing_walk": car_owners_choosing_walk,
               "would_use_car_count": would_use_car_count,
               "wouldnt_use_car_count": wouldnt_use_car_count,
           }, out_mask


def get_transit_modal_share(stats):
    """
    Get the transit modal share according to UPPER definition from the stats
    :param stats: the stats from get_modal_share
    :return: the transit modal share
    """
    total_car_meters = stats["total_car_meters"]
    total_transit_meters = stats["total_rail_meters"] + stats["total_bus_meters"]

    total_car_passengers = stats["total_car_passengers"]
    total_transit_passengers = stats["total_rail_passengers"] + stats["total_bus_passengers"]

    car_passenger_meters = total_car_meters * total_car_passengers
    transit_passenger_meters = total_transit_meters * total_transit_passengers

    total_passenger_meters = car_passenger_meters + transit_passenger_meters

    if total_passenger_meters == 0:
        return 0

    return transit_passenger_meters / total_passenger_meters


def get_all_modal_shares(stats):
    """
    Get the modal shares for all modes (distance travelled in mode x people using the mode)
    :param stats:
    :return:
    """
    car_pm = stats["total_car_meters"] * stats["total_car_passengers"]
    rail_pm = stats["total_rail_meters"] * stats["total_rail_passengers"]
    bus_pm = stats["total_bus_meters"] * stats["total_bus_passengers"]
    walk_pm = stats["total_walk_meters"] * stats["total_walkers"]

    total_pm = car_pm + rail_pm + bus_pm + walk_pm

    car_share = car_pm / total_pm
    rail_share = rail_pm / total_pm
    bus_share = bus_pm / total_pm
    walk_share = walk_pm / total_pm

    return {
        "car_share": car_share,
        "rail_share": rail_share,
        "bus_share": bus_share,
        "walk_share": walk_share,
    }


def push_stats_to_db(db, sim_id, stats, meta=None):
    stats_coll = db["stats"]

    doc = {
        "sim-id": sim_id,
        "stat-id": str(uuid.uuid4()),
        "created": datetime.datetime.now(),
        "base-stats": stats,
        "upper-transit-modal-share": get_transit_modal_share(stats),
        "modal-shares": get_all_modal_shares(stats),
    }

    if meta is not None:
        doc["meta"] = meta

    stats_coll.insert_one(doc)

    return doc


def run_decisions(db, sim_id, params=None):
    """
    Run decision algorithm without congestion simulation
    :param db: the database
    :param sim_id: the simulation id
    :return:
    """
    if params is None:
        params = Params()

    route_options = db["route-options"]

    results = route_options.find({"sim-id": sim_id})

    stats, _ = get_modal_share(results, params=params)

    print(stats)

    transit_modal_share = get_transit_modal_share(stats)

    print(f"Transit modal share: {transit_modal_share * 100}%")

    return stats


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

        stats, next_mask = get_modal_share(route_options, mask, delay_set)

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


common_cities = [
    {
        "name": "Paris 2019",
        "sim-id": "f23a4643-3bfb-44c8-8fa5-9bbd9aae880f",
        "inhabitants": 2000000
    },
    {
        "name": "Dublin 2019",
        "sim-id": "679d7a54-7e84-49d9-aa7a-d2ff1803c41c",
        "inhabitants": 500000
    },
    {
        "name": "Dublin County 2020",
        "sim-id": "f4153089-2217-4aea-91bd-18917355490e",  # "ae945a7c-5fa7-4312-b9c1-807cb30b3008",
        "inhabitants": 1400000
    },
    {
        "name": "Leuven 2019",
        "sim-id": "95edfe56-f277-44fb-bf23-289c67a8e593",
        "inhabitants": 100000
    }
]


def run_modal_share_for_some_cities():
    db = get_database()
    params = Params()

    for city in common_cities:
        print("Running for " + city["name"])
        params.car_usage_override = 1
        params.num_citizens = city["inhabitants"]
        stats = run_decisions(db, city["sim-id"], params)
        push_stats_to_db(db, city["sim-id"], stats, {
            "name": city["name"],
            "inhabitants": city["inhabitants"],
            "car_owner_override": params.car_usage_override,
            "method": "no-congestion,leg-based counts,car usage override"
        })


def __plot_monte_carlo_convergence(db, sim_id, city_name=None, params=None):
    """
    Run decision algorithm without congestion simulation on multiple subsets of the data and plots convergence
    :param db: the database
    :param sim_id: the simulation id
    :param city_name: the city name to add to the plot
    :param params: the parameters
    :return:
    """
    if params is None:
        params = Params()

    color_map = {
        "walk": "#D280CE",
        "car": "#FE5F55",
        "bus": "#F0B67F",
        "rail": "#F7F4D3"
    }
    background_color = "#030A13"

    route_options = db["route-options"]

    results = list(route_options.find({"sim-id": sim_id}))

    num_to_plot = 1
    num_steps = 100

    num_to_plot_add = int(len(results) / num_steps)

    modal_shares = []
    vc_count = []

    for i in range(num_steps):
        print("Running for " + str(num_to_plot) + " results")
        stats, _ = get_modal_share(results[:num_to_plot], params=params)
        modal_share = get_all_modal_shares(stats)
        modal_shares.append(modal_share)
        vc_count.append(num_to_plot)
        num_to_plot += num_to_plot_add

    # plot in 1920x1080

    walk_shares = [modal_share["walk_share"] for modal_share in modal_shares]
    rail_shares = [modal_share["rail_share"] for modal_share in modal_shares]
    bus_shares = [modal_share["bus_share"] for modal_share in modal_shares]
    car_shares = [modal_share["car_share"] for modal_share in modal_shares]

    # plot all to same graph

    plt.style.use('dark_background')

    plt.figure(figsize=(19.2, 10.8))

    plt.plot(vc_count, walk_shares, label="Walk", linewidth=4, color=color_map["walk"])
    plt.plot(vc_count, rail_shares, label="Rail", linewidth=4, color=color_map["rail"])
    plt.plot(vc_count, bus_shares, label="Bus", linewidth=4, color=color_map["bus"])
    plt.plot(vc_count, car_shares, label="Car", linewidth=4, color=color_map["car"])

    plt.tick_params(axis='both', which='major', labelsize=20, length=10, width=4)
    plt.xlabel("Number of virtual commuters", fontsize=24)
    plt.ylabel("Modal share", fontsize=24)
    if city_name is not None:
        plt.title(city_name, fontsize=26)
    plt.legend(fontsize=24, facecolor=background_color, edgecolor=background_color)
    plt.gca().set_facecolor(background_color)
    plt.gcf().set_facecolor(background_color)
    plt.savefig("modal_shares_" + city_name.lower().replace(" ", "") + "_1920x1080.png", dpi=100,
                facecolor=plt.gcf().get_facecolor())
    plt.show()


def plot_monte_carlo_convergence():
    db = get_database()
    params = Params()
    params.car_usage_override = 0

    for city in common_cities:
        print("Running for " + city["name"])
        params.num_citizens = city["inhabitants"]

        __plot_monte_carlo_convergence(db, city["sim-id"], city["name"], params)


def __plot_transit_monte_carlo_convergence(db, sim_id, city_name=None, params=None):
    """
    Run decision algorithm without congestion simulation on multiple subsets of the data and plots convergence
    :param db: the database
    :param sim_id: the simulation id
    :param city_name: the city name to add to the plot
    :param params: the parameters
    :return:
    """
    if params is None:
        params = Params()

    background_color = "#030A13"

    route_options = db["route-options"]

    results = list(route_options.find({"sim-id": sim_id}))

    num_to_plot = 1
    num_steps = 100

    num_to_plot_add = int(len(results) / num_steps)

    modal_shares = []
    vc_count = []

    for i in range(num_steps):
        print("Running for " + str(num_to_plot) + " results")
        stats, _ = get_modal_share(results[:num_to_plot], params=params)
        modal_share = get_transit_modal_share(stats)
        modal_shares.append(modal_share)
        vc_count.append(num_to_plot)
        num_to_plot += num_to_plot_add

    # plot all to same graph

    plt.style.use('dark_background')

    plt.figure(figsize=(19.2, 10.8))

    plt.plot(vc_count, modal_shares, linewidth=4, color="#D280CE")

    plt.tick_params(axis='both', which='major', labelsize=20, length=10, width=4)
    plt.xlabel("Number of virtual commuters", fontsize=24)
    plt.ylabel("Transit modal share", fontsize=24)
    if city_name is not None:
        plt.title(city_name, fontsize=26)
    plt.legend(fontsize=24, facecolor=background_color, edgecolor=background_color)
    plt.gca().set_facecolor(background_color)
    plt.gcf().set_facecolor(background_color)
    plt.savefig("transit_modal_shares_" + city_name.lower().replace(" ", "") + "_1920x1080.png", dpi=100,
                facecolor=plt.gcf().get_facecolor())
    plt.show()


def plot_transit_monte_carlo_convergence():
    db = get_database()
    params = Params()
    params.car_usage_override = 0

    for city in common_cities:
        print("Running for " + city["name"])
        params.num_citizens = city["inhabitants"]

        __plot_transit_monte_carlo_convergence(db, city["sim-id"], city["name"], params)


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

    journeys = list(congestion.find_all_journeys(db, sim_id))
    route_options = congestion.find_matching_route_options(db, sim_id, journeys)

    mask = [vc_extract.would_use_motorized_vehicle(route_option["traveller"]) for route_option in route_options]

    edges = congestion.get_edges(db, sim_id, journeys)

    congestion_set = congestion.get_congestion_set(journeys, edges, mask, vehicles_per_journey)
    # data = run_congestion_simulation(db, sim_id, params)

    nodes = congestion.get_nodes(db, sim_id, edges)

    return plot_congestion_for_set(f_map, congestion_set, nodes)


def plot_paris_congestion():
    image_name = "paris_congestion.png"
    html_file = "paris_congestion.html"

    city = common_cities[0]

    map_f = folium.Map(location=[48.857003, 2.3492646], zoom_start=13, tiles='CartoDB dark_matter', zoom_control=False)

    params = Params()
    params.num_citizens = city["inhabitants"]
    params.car_usage_override = 0

    plot_congestion_for_sim(map_f, city["sim-id"], params)

    map_f.save(html_file)

    abs_path = "file:///" + os.path.abspath(html_file)

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1920, 1080)

    driver.get(abs_path)
    time.sleep(0.2)
    driver.save_screenshot(image_name)


def analyze_waling_distances(city):
    sim_id = city["sim-id"]
    city_name = city["name"]

    db = get_database()
    params = Params()

    params.num_citizens = city["inhabitants"]

    journeys = list(db["route-options"].find({"sim-id": sim_id}))

    choices = [None] * len(journeys)

    get_modal_share(journeys, out_selection=choices, params=params)
    walk_distances = []

    for (i, journey) in enumerate(journeys):
        choice = choices[i]

        if choice is None:
            continue

        has_car = vc_extract.has_motor_vehicle(journey["traveller"])  # does the vc have a motorized vehicle?

        if has_car:
            continue

        for option in journey["options"]:
            option_id = option["route-option-id"]
            if option_id != choice:
                continue

            walk_distance = 0

            for leg in option["modes"]:
                if leg["mode"] == "walk":
                    walk_distance += leg["distance"]

            walk_distances.append(walk_distance)

    # plot histogram of walk distances
    plt.hist(walk_distances, bins=100)
    plt.title("Walk distances for " + city_name)
    plt.xlabel("Walk distance (m)")
    plt.ylabel("Number of journeys")
    plt.show()


def temp_dublin_calibration():
    # run modal share for dublin county
    db = get_database()
    params = Params()

    city = common_cities[2]

    params.num_citizens = city["inhabitants"]

    print("Running for " + city["name"])

    params.car_usage_override = 0
    params.car_ownership_override = 0.3 # 0.41

    params.num_citizens = city["inhabitants"]
    stats = run_decisions(db, city["sim-id"], params)

    transit_modal_share = get_transit_modal_share(stats)

    print(transit_modal_share)

    modal_shares = get_all_modal_shares(stats)
    print(modal_shares)


# todo use random.systemrandom() instead of random.random() for better randomness
if __name__ == "__main__":
    # plot_vehicle_factors("735a3098-8a19-4252-9ca8-9372891e90b3")
    # plot_congestion_for_sim("0ee97ddf-333e-4f62-b3de-8d7f52459065")

    # run_modal_share_for_some_cities()
    # plot_monte_carlo_convergence()
    # plot_transit_monte_carlo_convergence()
    # plot_paris_congestion()
    # analyze_waling_distances(common_cities[2])
    plot_monte_carlo_convergence()
    # plot_transit_monte_carlo_convergence()



