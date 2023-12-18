import datetime
import random
import uuid

import osmnx
from matplotlib import pyplot as plt

import hiveline.vc.vc_extract as vc_extract
from hiveline.od.place import Place
from hiveline.results.journeys import Journeys, Option, Options, get_option_stats, JourneyStats
from hiveline.routing import fptf
from hiveline.routing.util import ensure_directory

rail_modes = [fptf.Mode.TRAIN, fptf.Mode.BUS, fptf.Mode.GONDOLA, fptf.Mode.WATERCRAFT]


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


def decide(options: Options, params: Params = None) -> Option | None:
    """
    Decide on a route option
    :param options: the route options
    :param params: the simulation parameters
    :return: the chosen route option
    """
    if params is None:
        params = Params()

    would_use_car = vc_extract.would_use_motorized_vehicle(
        options.traveller.to_dict())  # would the vc use a motorized vehicle?

    has_car = vc_extract.has_motor_vehicle(options.traveller.to_dict())  # does the vc have a motorized vehicle?

    if not has_car and random.random() < params.car_ownership_override:
        has_car = True
        would_use_car = True

    if not would_use_car and has_car and random.random() < params.car_usage_override:
        would_use_car = True

    valid_options = options.options

    if not would_use_car:
        valid_options = [o for o in valid_options if not o.has_car()]

    if len(valid_options) == 0:
        return None

    durations = [o.journey.duration() for o in valid_options]
    durations = [d if d is not None else 0 for d in durations]

    return valid_options[durations.index(min(durations))]  # choose the fastest option


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


def merge_journey_stats(stats: list[JourneyStats]) -> JourneyStats:
    result = JourneyStats()
    result.car_meters = sum([s.car_meters for s in stats])
    result.rail_meters = sum([s.rail_meters for s in stats])
    result.bus_meters = sum([s.bus_meters for s in stats])
    result.walk_meters = sum([s.walk_meters for s in stats])

    result.car_passengers = sum([s.car_passengers for s in stats])
    result.rail_passengers = sum([s.rail_passengers for s in stats])
    result.bus_passengers = sum([s.bus_passengers for s in stats])
    result.walkers = sum([s.walkers for s in stats])

    return result


def get_journeys_stats(journeys: Journeys, params: Params = None, max_count=None) -> JourneyStats:
    """
    Get the modal share for a set of route options
    :param journeys: the journeys
    :param params: (optional) the simulation parameters
    :param max_count: (optional) the maximum number of route options to consider
    :return: a dictionary with the modal share
    """
    if params is None:
        params = Params()

    selection = journeys.get_selection(lambda options: decide(options, params), max_count=max_count)

    option_stats = [get_option_stats(option) for option in journeys.iterate_selection(selection)]

    return merge_journey_stats(option_stats)


def push_stats_to_db(db, sim_id, stats: JourneyStats, meta=None):
    stats_coll = db["stats"]

    doc = {
        "sim-id": sim_id,
        "stat-id": str(uuid.uuid4()),
        "created": datetime.datetime.now(),
        "base-stats": stats,
        "upper-transit-modal-share": stats.get_transit_modal_share(),
        "modal-shares": stats.get_all_modal_shares(),
    }

    if meta is not None:
        doc["meta"] = meta

    stats_coll.insert_one(doc)

    return doc


def plot_monte_carlo_convergence(journeys: Journeys, city_name: str, use_city_bounds=False, params=None):
    """
    Run decision algorithm without congestion simulation on multiple subsets of the data and plots convergence
    :param journeys: the journeys
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

    num_to_plot = 1
    num_steps = 100

    shape = None

    if use_city_bounds:
        place = Place(city_name)
        shape = place.shape.iloc[0].geometry

    t = datetime.datetime.now()

    selection = journeys.get_selection(lambda options: decide(options, params))

    stats = [get_option_stats(option, shape=shape) for option in journeys.iterate_selection(selection)]
    print(f"Calculating stats took {(datetime.datetime.now() - t).total_seconds()} seconds")

    num_to_plot_add = int(len(journeys.options) / num_steps)

    modal_shares = []
    vc_count = []

    for i in range(num_steps):
        sub_stats = merge_journey_stats(stats[:num_to_plot])
        modal_share = sub_stats.get_all_modal_shares()
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
    plt.savefig("modal_shares_" + (city_name or "").lower().replace(" ", "") + "_1920x1080.png", dpi=100,
                facecolor=plt.gcf().get_facecolor())
    plt.show()


def plot_transit_monte_carlo_convergence(journeys: Journeys, city_name=None, params=None):
    """
    Run decision algorithm without congestion simulation on multiple subsets of the data and plots convergence
    :param journeys: the journeys
    :param city_name: the city name to add to the plot
    :param params: the parameters
    :return:
    """
    if params is None:
        params = Params()

    background_color = "#030A13"

    num_to_plot = 1
    num_steps = 100

    num_to_plot_add = int(len(journeys.options) / num_steps)

    modal_shares = []
    vc_count = []

    for i in range(num_steps):
        print("Running for " + str(num_to_plot) + " results")
        stats = get_journeys_stats(journeys, params=params, max_count=num_to_plot)
        modal_share = stats.get_transit_modal_share()
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


def analyze_waling_distances(journeys: Journeys, city_name=None):
    params = Params()

    selection = journeys.get_selection(lambda options: decide(options, params))
    walk_distances = []

    for option in journeys.iterate_selection(selection):
        option_stats = get_option_stats(option)
        walk_distances.append(option_stats.walk_meters)

    # plot histogram of walk distances
    plt.hist(walk_distances, bins=100)
    plt.title("Walk distances for " + city_name)
    plt.xlabel("Walk distance (m)")
    plt.ylabel("Number of journeys")
    plt.show()


# todo use random.systemrandom() instead of random.random() for better randomness
if __name__ == "__main__":
    # t = datetime.datetime.now()
    # jrn = Journeys("bd6809da-8113-469f-91cc-501549e8df68")
    # print(f"Loading journeys took {(datetime.datetime.now() - t).total_seconds()} seconds")
    #
    # plot_monte_carlo_convergence(jrn, "Eindhoven suburbs, Netherlands")
    # plot_monte_carlo_convergence(jrn, "Eindhoven, Netherlands", use_city_bounds=True)

    bounds_dir = "./cache/place-bounds"
    ensure_directory(bounds_dir)

    with open(bounds_dir + "/eindhoven.json", "w") as f:
        f.write(osmnx.geocode_to_gdf("Eindhoven, Netherlands").to_json(to_wgs84=True))
