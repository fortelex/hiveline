if __name__ == "__main__":
    import sys
    import os
    from dotenv import load_dotenv

    load_dotenv()

    sys.path.append(os.getenv("PROJECT_PATH"))

import argparse
import datetime
import time
import uuid

import pymongo.errors

from hiveline.jobs.jobs import JobHandler, JobStatus
from hiveline.jobs.mongo import MongoJobsDataSource
from hiveline.models import fptf
from hiveline.models.options import Option
from hiveline.mongo.db import get_database
from hiveline.routing import resource_builder
from hiveline.routing.clients.delayed import DelayedRoutingClient
from hiveline.routing.clients.routing_client import RoutingClient
from hiveline.routing.servers.routing_server import RoutingServer
from hiveline.vc import vc_extract


def __create_route_calculation_jobs(db, sim_id, job_handler):
    """
    Create route calculation jobs for all virtual commuters of a given simulation that do not have a job yet.
    :param db: the database
    :param sim_id: the simulation id
    :return:
    """
    pipeline = [
        {
            "$match": {
                "sim-id": sim_id
            }
        },
        {
            "$project": {
                "vc-id": "$vc-id",
            }
        }
    ]

    coll = db["virtual-commuters"]

    result = coll.aggregate(pipeline)
    job_ids = [vc["vc-id"] for vc in result]

    job_handler.create_jobs(job_ids)


def __get_route_results(client: RoutingClient, vc: dict, sim: dict, modes: list[fptf.Mode]) -> list[Option] | None:
    """
    Get a route for a virtual commuter.
    :param client: The routing client
    :param vc: The virtual commuter
    :param sim: The simulation
    :param modes: The modes to use
    :return:
    """
    origin = vc_extract.extract_origin_loc(vc)
    destination = vc_extract.extract_destination_loc(vc)
    departure = vc_extract.extract_departure(vc, sim)

    journeys = client.get_journeys(origin[1], origin[0], destination[1], destination[0], departure, modes)

    if journeys is None:
        return None

    origin_fptf = fptf.Location(longitude=origin[0], latitude=origin[1])
    destination_fptf = fptf.Location(longitude=destination[0], latitude=destination[1])

    return [Option(str(uuid.uuid4()), origin_fptf, destination_fptf, departure, modes, journey) for journey in journeys]


def __route_virtual_commuter(client: RoutingClient, vc: dict, sim: dict) -> list[Option]:
    """
    Route a virtual commuter. It will calculate available mode combinations and then calculate routes for each of them.
    :param client: The routing client
    :param vc: The virtual commuter
    :param sim: The simulation
    :return:
    """
    mode_combinations = [[fptf.Mode.WALKING, fptf.Mode.BUS, fptf.Mode.TRAIN, fptf.Mode.GONDOLA]]

    #  if vc_extract.has_motor_vehicle(vc):
    mode_combinations += [[fptf.Mode.WALKING, fptf.Mode.CAR]]

    option_lists = [__get_route_results(client, vc, sim, modes) for modes in mode_combinations]
    options = []

    for option_list in option_lists:
        if option_list is None:
            continue
        options += option_list

    options = [option for option in options if option is not None]

    return options


def __process_virtual_commuter(client, route_results_coll, vc_coll, vc_id, sim, meta):
    vc = vc_coll.find_one({"vc-id": vc_id, "sim-id": sim["sim-id"]})

    should_route = vc_extract.should_route(vc)

    if not should_route:
        return

    options = __route_virtual_commuter(client, vc, sim)

    if options is None or len(options) == 0:
        print("No route found for virtual commuter " + vc["vc-id"])
        raise Exception("No route found")

    # dump options to route-results collection
    route_results = {
        "vc-id": vc["vc-id"],
        "sim-id": vc["sim-id"],
        "created": datetime.datetime.now(),
        "options": [option.to_dict() for option in options],
        "traveller": vc_extract.extract_traveller(vc),
        "meta": meta
    }

    try:
        route_results_coll.insert_one(route_results)
    except pymongo.errors.DuplicateKeyError:
        if "_id" in route_results:
            del route_results["_id"]
        route_results_coll.update_one({"vc-id": vc["vc-id"], "sim-id": vc["sim-id"]}, {"$set": route_results})


def __route_virtual_commuters(server: RoutingServer, client: RoutingClient, sim_id, data_dir="./cache", use_delays=True,
                              force_graph_rebuild=False, num_threads=4, reset_jobs=False, reset_failed=False, db=None):
    """
    Run the routing algorithm for a virtual commuter set. It will spawn a new OTP process and run the routing algorithm
    for all open jobs in the database. It will also update the database with the results of the routing algorithm.

    :param server: The routing server
    :param client: The routing client
    :param sim_id: The virtual commuter set id
    :param data_dir: The directory where the data should be stored
    :param use_delays: Whether to use delays or not
    :param force_graph_rebuild: Whether to force a rebuild of the graph or not
    :param num_threads: The number of threads to use for sending route requests to the server
    :param reset_jobs: Whether to reset all jobs to pending or not
    :param reset_failed: Whether to reset all failed jobs to pending or not
    :param db: The database
    :return:
    """
    if db is None:
        db = get_database()

    job_handler = JobHandler("routing", sim_id, MongoJobsDataSource(db=db))

    if reset_jobs:
        job_handler.reset_jobs()

    if reset_failed and not reset_jobs:
        job_handler.reset_failed_jobs()

    __create_route_calculation_jobs(db, sim_id, job_handler)
    job_handler.reset_timed_out_jobs()

    if job_handler.count_jobs(status=JobStatus.PENDING) == 0:
        print("No active jobs, stopping")
        return

    sim = db["simulations"].find_one({"sim-id": sim_id})
    place_resources = db["place-resources"].find_one({"place-id": sim["place-id"]})
    sim_date = datetime.datetime.strptime(sim["sim-date"], "%Y-%m-%d").date()

    print("Building resources")
    config = resource_builder.build_resources(data_dir, place_resources, sim_date)
    print("Built resources. Building graph")

    server_files = server.build(config, force_rebuild=force_graph_rebuild)

    print("Graph built")
    print("Starting server...")

    meta = {
        "osm": [{"source": source} for source in config.osm_files],
        "gtfs": [{"source": source} for source in config.gtfs_files],
        "router": server.get_meta(),
        "uses-delay-simulation": use_delays
    }

    route_results_coll = db["route-results"]
    vc_coll = db["virtual-commuters"]

    server.start(config, server_files)

    try:
        print("Server started")

        t = datetime.datetime.now()

        job_handler.iterate_jobs(
            lambda job_id: __process_virtual_commuter(client, route_results_coll, vc_coll, job_id, sim, meta),
            threads=num_threads, debug_progress=True)

        print("Finished routing algorithm in " + str(datetime.datetime.now() - t))

    finally:
        server.stop()

        print("Server stopped")


def __get_profile_without_delay(profile_str: str, threads=12, memory_gb: int = 4, api_timeout: float = 10,
                                client_timeout: float = 20) -> [RoutingServer, RoutingClient]:
    if profile_str == "opentripplanner":
        from hiveline.routing.servers.otp import OpenTripPlannerRoutingServer
        from hiveline.routing.clients.otp import OpenTripPlannerRoutingClient

        return OpenTripPlannerRoutingServer(memory_gb=memory_gb, api_timeout=api_timeout), OpenTripPlannerRoutingClient(
            client_timeout=client_timeout)
    elif profile_str == "bifrost":
        from hiveline.routing.servers.bifrost import BifrostRoutingServer
        # from hiveline.routing.servers.no_server import NoServer

        from hiveline.routing.clients.bifrost import BifrostRoutingClient

        return BifrostRoutingServer(threads=threads), BifrostRoutingClient(client_timeout=client_timeout)
        # return NoServer(), BifrostRoutingClient(client_timeout=client_timeout)

    raise Exception("Unknown profile: " + profile_str)


def __get_profile(profile_str: str, use_delays: bool = False, threads=4, memory_gb: int = 4, api_timeout: float = 10,
                  client_timeout: float = 20) -> [RoutingServer, RoutingClient]:
    [server, client] = __get_profile_without_delay(profile_str, threads=threads, memory_gb=memory_gb,
                                                   api_timeout=api_timeout, client_timeout=client_timeout)
    if use_delays:
        return server, DelayedRoutingClient(client)
    return server, client


def route_virtual_commuters(sim_id, profile="opentripplanner", data_dir="./cache", use_delays=True,
                            force_graph_rebuild=False, memory_gb=4, num_threads=4,
                            reset_jobs=False, reset_failed=False, timeout=20):
    """
    Run the routing algorithm for a virtual commuter set. It will spawn a new process and run the routing algorithm
    for all open jobs in the database. It will also update the database with the results of the routing algorithm.
    :param sim_id: The virtual commuter set id
    :param profile: The profile to use for the routing server and client (opentripplanner, bifrost, ...)
    :param data_dir: The directory where the data should be stored
    :param use_delays: Whether to use delays or not
    :param force_graph_rebuild: Whether to force a rebuild of the graph or not
    :param memory_gb: The amount of memory to use for the build process and server
    :param num_threads: The number of threads to use for sending route requests to the server
    :param reset_jobs: Whether to reset all jobs to pending or not
    :param reset_failed: Whether to reset all failed jobs to pending or not
    :param timeout: The timeout for the client (in seconds), server will use half of that as API timeout
    :return:
    """

    profile_server, profile_client = __get_profile(profile, use_delays, threads=num_threads, memory_gb=memory_gb,
                                                   client_timeout=timeout, api_timeout=timeout / 2)
    __route_virtual_commuters(profile_server, profile_client, sim_id, data_dir=data_dir, use_delays=use_delays,
                              force_graph_rebuild=force_graph_rebuild, num_threads=num_threads, reset_jobs=reset_jobs,
                              reset_failed=reset_failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the routing algorithm for a virtual commuter set')
    parser.add_argument('sim_id', type=str, help='Simulation id')
    parser.add_argument("--profile", dest="profile", type=str, default="opentripplanner",
                        help="The profile to use for the routing server and client (opentripplanner, bifrost, ...)")
    parser.add_argument("--data-dir", dest="data_dir", type=str, default="./cache",
                        help="The directory where the data should be stored")
    parser.add_argument('--no-delays', dest='no_delays', action='store_true', help='Whether to use delays or not')
    parser.add_argument('--force-graph-rebuild', dest='force_graph_rebuild', action='store_true', help='Whether to '
                                                                                                       'force a rebuild of the graph or not')
    parser.add_argument('--memory', dest='memory_db', type=int, default=4, help='The amount of memory to '
                                                                                'use for the server and client (in GB)')
    parser.add_argument('--num-threads', dest='num_threads', type=int, default=4, help='The number of threads to use '
                                                                                       'for sending route requests to the server')
    parser.add_argument('--reset-jobs', dest='reset_jobs', action='store_true', help='Whether to reset all jobs for '
                                                                                     'this simulation')
    parser.add_argument('--reset-failed', dest='reset_failed', action='store_true', help='Whether to reset all failed '
                                                                                         'jobs for this simulation')
    parser.add_argument('--timeout', dest='timeout', type=int, default=20,
                        help='The timeout for the client (in seconds), server will use half of that as API timeout')

    args = parser.parse_args()

    try:
        route_virtual_commuters(args.sim_id, args.profile, args.data_dir, not args.no_delays, args.force_graph_rebuild,
                                args.memory_db, args.num_threads, args.reset_jobs, args.reset_failed, args.timeout)
    except Exception as e:
        print("Exception occurred while running routing algorithm: " + e.__class__.__name__ + ": " + str(e))
        time.sleep(10000)
