import argparse
import math
import os
import signal
import uuid
from datetime import datetime

import pymongo.errors

import otp
import otp_builder as builder
from mongo.mongo import get_database


def __create_route_calculation_jobs(db):
    """
    Create route calculation jobs for all virtual commuters that do not have a job yet.
    :param db: the database
    :return:
    """
    pipeline = [
        {
            "$lookup": {
                "from": "route-calculation-jobs",
                "localField": "vc-id",
                "foreignField": "vc-id",
                "as": "matched_docs"
            }
        },
        {
            "$match": {
                "matched_docs": {
                    "$size": 0
                }
            }
        }
    ]

    coll = db["virtual-commuters"]

    result = coll.aggregate(pipeline)
    jobs_coll = db["route-calculation-jobs"]

    for doc in result:
        vc_id = doc["vc-id"]
        vc_set_id = doc["vc-set-id"]
        created = datetime.now()

        job = {
            "vc-id": vc_id,
            "vc-set-id": vc_set_id,
            "created": created,
            "status": "pending"
        }

        try:
            jobs_coll.insert_one(job)
        except pymongo.errors.DuplicateKeyError:
            continue  # job was created by other process while iterating


def __get_route_option(vc, uses_delays, modes):
    """
    Get a route for a virtual commuter.
    :param vc: The virtual commuter
    :param uses_delays: Whether to use delay simulation or not
    :param modes: The modes to use
    :return:
    """
    origin = vc["origin"]["coordinates"]
    destination = vc["destination"]["coordinates"]
    departure = vc["departure"]

    departure_date = departure.strftime("%Y-%m-%d")
    departure_time = departure.strftime("%H:%M")

    if uses_delays:
        itinerary = otp.get_delayed_route(origin[1], origin[0], destination[1], destination[0], departure_date,
                                          departure_time, False, modes)
        if itinerary is None:
            return None

        itineraries = [itinerary]

    else:
        itineraries = otp.get_route(origin[1], origin[0], destination[1], destination[0], departure_date,
                                    departure_time,
                                    False, modes)

    if itineraries is None or len(itineraries) == 0:
        return None

    return {
        "route-option-id": str(uuid.uuid4()),
        "origin": vc["origin"],
        "destination": vc["destination"],
        "departure": vc["departure"],
        "modes": modes,
        "itineraries": itineraries
    }


def __route_virtual_commuter(vc, uses_delays):
    """
    Route a virtual commuter. It will calculate available mode combinations and then calculate routes for each of them.
    :param vc:
    :param uses_delays:
    :return:
    """
    mode_combinations = [["WALK", "TRANSIT"]]

    if "traveller" in vc and "would-use-car" in vc["traveller"] and vc["traveller"]["would-use-car"]:
        mode_combinations += [["WALK", "CAR"]]

    return [__get_route_option(vc, uses_delays, modes) for modes in mode_combinations]


def __approx_dist(origin, destination):
    """
    Approximate the distance between two points in meters using the Haversine formula.

    :param origin: object with fields lon, lat
    :param destination: object with fields lon, lat
    :return: distance in meters
    """

    # Convert latitude and longitude from degrees to radians
    lon1 = math.radians(origin["lon"])
    lat1 = math.radians(origin["lat"])
    lon2 = math.radians(destination["lon"])
    lat2 = math.radians(destination["lat"])

    # Radius of the Earth in kilometers
    R = 6371.0

    # Difference in coordinates
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    # Haversine formula
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in kilometers
    distance_km = R * c

    # Convert to meters
    distance_meters = distance_km * 1000

    return distance_meters


def __extract_mode_data(leg):
    """
    Extract relevant data from a leg.
    :param leg: The trip leg of an itinerary
    :return: an object with mode, duration (in seconds) and distance (in meters)
    """
    mode = leg["mode"].lower()
    start_time = leg["startTime"]
    if "rtStartTime" in leg:
        start_time = leg["rtStartTime"]
    end_time = leg["endTime"]
    if "rtEndTime" in leg:
        end_time = leg["rtEndTime"]
    duration = (end_time - start_time) / 1000

    origin = leg["from"]
    destination = leg["to"]

    # TODO: distance can be better calculated using steps or shapes
    distance = __approx_dist(origin, destination)

    return {
        "mode": mode,
        "duration": duration,
        "distance": distance
    }


def __extract_relevant_data(route_details):
    """
    Extract relevant data from a route details object.

    :param route_details: Route details. The output of __get_route_option
    :return: An object with route-option-id, route-duration (in s), route-changes, route-delay (in s),
             route-recalculated, modes (array of objects with mode, duration (in s) and distance (in m))
    """
    itinerary = route_details["itineraries"][0]
    start_time = itinerary["startTime"]
    end_time = itinerary["endTime"]
    actual_end_time = end_time
    if "rtEndTime" in itinerary:
        actual_end_time = itinerary["rtEndTime"]

    delay = (actual_end_time - end_time) / 1000
    duration = (actual_end_time - start_time) / 1000

    changes = -1

    for leg in itinerary["legs"]:
        if leg["mode"] == "WALK":
            continue
        changes += 1

    if changes == -1:
        changes = 0

    modes = [__extract_mode_data(leg) for leg in itinerary["legs"]]

    return {
        "route-option-id": route_details["route-option-id"],
        "route-duration": duration,
        "route-changes": changes,
        "route-delay": delay,
        "route-recalculations": itinerary["reCalcCount"],
        "modes": modes
    }


def __no_active_jobs(db, vc_set_id):
    jobs_coll = db["route-calculation-jobs"]
    return jobs_coll.count_documents({"vc-set-id": vc_set_id, "status": "pending"}) == 0


def __iterate_jobs(db, vc_set_id, meta):
    """
    Iterate over all pending jobs in the database for a virtual commuter set and calculate routes for them.
    :param db: the database
    :param vc_set_id: the virtual commuter set id
    :param meta: metadata about the routing process
    :return: Nothing, all data is pushed to database
    """
    jobs_coll = db["route-calculation-jobs"]
    route_results_coll = db["route-results"]
    route_options_coll = db["route-options"]

    pipeline = [
        {
            "$match": {
                "status": "pending",
                "vc-set-id": vc_set_id
            }
        },
        {
            "$lookup": {
                "from": "virtual-commuters",
                "localField": "vc-id",
                "foreignField": "vc-id",
                "as": "matched_docs"
            }
        },
        {
            "$match": {
                "matched_docs": {
                    "$size": 1
                }
            }
        }
    ]

    use_delays = meta["uses-delay-simulation"]

    jobs_to_calculate = jobs_coll.aggregate(pipeline)

    # by default, we will not stop the process if there is one error, but if there are multiple consecutive errors,
    # we will stop the process
    consecutive_error_number = 0

    for doc in jobs_to_calculate:
        if doc["status"] != "pending":
            continue

        # set status to running
        jobs_coll.update_one({"_id": doc["_id"]}, {"$set": {"status": "running", "started": datetime.now()}})

        print("Running routing algorithm")

        try:
            vc = doc["matched_docs"][0]
            options = __route_virtual_commuter(vc, use_delays)

            if options is None:
                raise Exception("No route found")

            # dump options to route-results collection
            route_results = {
                "vc-id": vc["vc-id"],
                "vc-set-id": vc["vc-set-id"],
                "created": datetime.now(),
                "options": options,
                "meta": meta
            }

            try:
                route_results_coll.insert_one(route_results)
            except pymongo.errors.DuplicateKeyError:
                if "_id" in route_results:
                    del route_results["_id"]
                route_results_coll.update_one({"vc-id": vc["vc-id"]}, {"$set": route_results})

            # extract relevant data for decision making
            route_options = {
                "vc-id": vc["vc-id"],
                "vc-set-id": vc["vc-set-id"],
                "created": datetime.now(),
                "traveller": vc["traveller"],
                "options": [__extract_relevant_data(option) for option in options],
            }

            try:
                route_options_coll.insert_one(route_options)
            except pymongo.errors.DuplicateKeyError:
                if "_id" in route_options:
                    del route_options["_id"]
                route_options_coll.update_one({"vc-id": vc["vc-id"]}, {"$set": route_options})

            # set status to finished
            jobs_coll.update_one({"_id": doc["_id"]}, {"$set": {"status": "done", "finished": datetime.now()}})

            consecutive_error_number = 0
        except Exception as e:
            short_description = "Exception occurred while running routing algorithm: " + e.__class__.__name__ + ": " \
                                + str(e)

            print(short_description)

            # set status to failed
            jobs_coll.update_one({"_id": doc["_id"]},
                                 {"$set": {"status": "error", "error": short_description, "finished": datetime.now()}})

            consecutive_error_number += 1

            if consecutive_error_number >= 5:
                print("Too many consecutive errors, stopping")
                break


def __wait_for_line(process, line_to_wait_for):
    """
    Wait for a specific line to appear in the output of a process

    :param process: the process
    :param line_to_wait_for: the line to wait for
    :return:
    """
    for line in iter(process.stdout.readline, b''):
        print(line, end='')  # Optional: print the line
        if line_to_wait_for in line:
            break


def run(vc_set_id, use_delays=True, force_graph_rebuild=False):
    """
    Run the routing algorithm for a virtual commuter set. It will spawn a new OTP process and run the routing algorithm
    for all open jobs in the database. It will also update the database with the results of the routing algorithm.
    :param vc_set_id: The virtual commuter set id
    :param use_delays: Whether to use delays or not
    :param force_graph_rebuild: Whether to force a rebuild of the graph or not
    :return:
    """
    db = get_database()

    __create_route_calculation_jobs(db)

    if __no_active_jobs(db, vc_set_id):
        print("No active jobs, stopping")
        return

    vc_set = db["virtual-commuters-sets"].find_one({"vc-set-id": vc_set_id})
    place_resources = db["place-resources"].find_one({"place-id": vc_set["place-id"]})
    pivot_date = vc_set["pivot-date"]

    resources = builder.build_graph(place_resources, pivot_date, force_graph_rebuild)

    proc = builder.run_server(resources["graph_file"])

    meta = {
        "otp-version": resources["otp_version"],
        "osm-dataset-link": resources["osm_source"]["source"],
        "osm-dataset-date": resources["osm_source"]["date"],
        "gtfs": [{"source": source["source"], "date": source["date"], "provider": source["provider"]} for source in
                 resources["gtfs_source"]],
        "uses-delay-simulation": use_delays
    }

    if proc is None:
        print("Server not started")
        exit(1)

    try:
        __wait_for_line(proc, "Grizzly server running.")  # that is the last line printed by the server when it is ready
        print("Server started")

        __iterate_jobs(db, vc_set_id, meta)

    finally:
        print("Terminating server...")

        try:
            os.kill(proc.pid, signal.CTRL_C_EVENT)  # clean shutdown with CTRL+C

            proc.wait()
        except KeyboardInterrupt:
            pass

        print("Server terminated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the routing algorithm for a virtual commuter set')
    parser.add_argument('vc_set_id', type=str, help='The virtual commuter set id')
    parser.add_argument('--no-delays', dest='no_delays', action='store_true', help='Whether to use delays or not')
    parser.add_argument('--force-graph-rebuild', dest='force_graph_rebuild', action='store_true', help='Whether to '
                                                                                                       'force a rebuild of the graph or not')

    args = parser.parse_args()

    run(args.vc_set_id, not args.no_delays, args.force_graph_rebuild)
