import os
import re
import threading
import time
from datetime import datetime

import argparse
import osmnx as ox
import pymongo.errors

from mongo.mongo import get_database
import historical_osmnx


def __create_matching_jobs(db, sim_id):
    """
    Create matching jobs for all route results that contain an option with CAR mode do not have a job yet
    :param db: the database
    :param sim_id: the simulation id
    :return:
    """
    pipeline = [
        {
            "$match": {
                "sim-id": sim_id,
                "options": {
                    "$elemMatch": {
                        "modes": "CAR",
                    }
                },
            },
        },
        {
            "$lookup": {
                "from": "matching-jobs",
                "localField": "vc-id",
                "foreignField": "vc-id",
                "as": "matching-jobs"
            },
        },
        {
            "$match": {
                "matching-jobs": {
                    "$size": 0
                }
            }
        },
        {
            "$project": {
                "vc-id": 1,
            }
        }
    ]

    coll = db["route-results"]

    result = coll.aggregate(pipeline)
    jobs_coll = db["matching-jobs"]

    for route_result in result:
        vc_id = route_result["vc-id"]
        created = datetime.now()

        job = {
            "vc-id": vc_id,
            "sim-id": sim_id,
            "created": created,
            "status": "pending",
        }

        try:
            jobs_coll.insert_one(job)
        except pymongo.errors.DuplicateKeyError:
            continue  # job was created by another process


def __reset_jobs(db, sim_id):
    """
    Reset all jobs for the given simulation to pending.
    :param db: the database
    :return:
    """

    coll = db["matching-jobs"]
    coll.update_many({"sim-id": sim_id},
                     {"$set": {"status": "pending"}, "$unset": {"error": "", "started": "", "finished": ""}})


def __no_active_jobs(db, sim_id):
    jobs_coll = db["matching-jobs"]
    return jobs_coll.count_documents({"sim-id": sim_id, "status": "pending"}) == 0


def __process_route_result(route_results_coll, route_result, graph, graph_undirected):
    """
    Run matching algorithm for a single route result.
    :param route_results_coll: The collection to update the route result in
    :param route_result: The route result to process
    :param graph: The graph to use for the matching
    :param graph_undirected: The undirected version of graph
    :return:
    """
    has_changed = False

    for option in route_result["options"]:
        if option is None:
            continue

        modes = option["modes"]
        if "CAR" not in modes:
            continue

        for itinerary in option["itineraries"]:
            for leg in itinerary["legs"]:
                if leg["mode"] != "CAR":
                    continue

                if "osm_nodes" in leg:
                    continue

                path = [(leg["from"]["lon"], leg["from"]["lat"])]

                for step in leg["steps"]:
                    path.append((step["lon"], step["lat"]))

                path.append((leg["to"]["lon"], leg["to"]["lat"]))

                node_ids = ox.nearest_nodes(graph, [p[0] for p in path], [p[1] for p in path])

                origins = node_ids[:-1]
                destinations = node_ids[1:]

                routes = ox.shortest_path(graph_undirected, origins, destinations, weight='length')

                first = routes[0][0]
                route = [first] + [item for sublist in routes for item in sublist[1:]]

                leg["osm_nodes"] = route

                has_changed = True

    if not has_changed:
        return

    route_results_coll.replace_one({"_id": route_result["_id"]}, route_result)


def __iterate_jobs(db, sim_id, graph, graph_undirected, debug=False, progress_fac=1):
    """
    Iterate over all matching jobs and run the matching algorithm for each job.
    :param db: the database
    :param sim_id: the simulation id
    :param graph: the graph to use for the matching
    :param graph_undirected: the undirected version of graph
    :param debug: if True, print debug information
    :param progress_fac: the progress factor to use (useful for debugging parallel processing)
    :return:
    """
    jobs_coll = db["matching-jobs"]
    route_results_coll = db["route-results"]

    # get total number of jobs
    total_jobs = jobs_coll.count_documents({"sim-id": sim_id, "status": "pending"})

    if total_jobs == 0:
        return

    if debug:
        print("Running matching algorithm")

    # by default, we will not stop the process if there is one error, but if there are multiple consecutive errors,
    # we will stop the process
    consecutive_error_number = 0

    job_key = 0
    last_print = 0

    while True:
        job = jobs_coll.find_one_and_update({
            "sim-id": sim_id,
            "status": "pending",
        }, {
            "$set": {
                "status": "running",
                "started": datetime.now(),
            }
        })

        if job is None:
            break

        job_key += 1

        percentage = job_key / total_jobs * 100
        current_time = time.time()
        if debug and current_time - last_print > 1:
            print("Progress: ~{:.2f}% {:}".format(percentage * progress_fac, job["vc-id"]))
            last_print = current_time

        try:
            route_result = route_results_coll.find_one({"vc-id": job["vc-id"], "sim-id": sim_id})
            __process_route_result(route_results_coll, route_result, graph, graph_undirected)

            # set status to finished
            jobs_coll.update_one({"_id": job["_id"]}, {
                "$set": {
                    "status": "finished",
                    "finished": datetime.now(),
                }
            })

        except Exception as e:
            short_description = "Exception occurred while running matching algorithm: " + e.__class__.__name__ + ": " \
                                + str(e)

            print(short_description)

            # set status to failed
            jobs_coll.update_one({"_id": job["_id"]},
                                 {"$set": {"status": "error", "error": short_description, "finished": datetime.now()}})

            consecutive_error_number += 1

            if consecutive_error_number >= 5:
                print("Too many consecutive errors, stopping")
                break


def __spawn_job_pull_threads(db, sim_id, graph, graph_undirected, num_threads=4):
    """
    Spawn threads to pull jobs from the database and run the matching algorithm for each job.
    :param db: the database
    :param sim_id: the simulation id
    :param graph: the graph to use for the matching
    :param graph_undirected: the undirected version of graph
    :param num_threads: the number of threads to spawn
    :return:
    """
    threads = []

    for i in range(num_threads):
        t = threading.Thread(target=__iterate_jobs, args=(db, sim_id, graph, graph_undirected, i == 0, num_threads))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


def run_matching(sim_id, place_name=None, num_threads=4, reset_jobs=False):
    """
    Run the matching algorithm for the given simulation id.
    :param sim_id: the simulation id
    :param place_name: the place name
    :param num_threads: the number of threads to use
    :param reset_jobs: if True, reset all jobs of the simulation
    :return:
    """
    db = get_database()

    __create_matching_jobs(db, sim_id)
    if reset_jobs:
        __reset_jobs(db, sim_id)

    if __no_active_jobs(db, sim_id):
        print("No active jobs, exiting. Use --reset-jobs to reset all jobs.")
        return

    graph = historical_osmnx.get_graph(db, sim_id, place_name, undirected=False)
    graph_undirected = historical_osmnx.get_graph(db, sim_id, place_name, undirected=True)

    print("Graph loaded.")

    t = time.time()
    __spawn_job_pull_threads(db, sim_id, graph, graph_undirected, num_threads=num_threads)
    print("Matching algorithm finished in {:.2f} seconds".format(time.time() - t))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the matching algorithm for the given simulation id.')
    parser.add_argument('sim_id', type=str, help='the simulation id')
    parser.add_argument('--place-name', type=str,
                        help='the place name. If not provided, the place name will fallback to the one in the database')
    parser.add_argument('--num-threads', type=int, default=4, help='the number of threads to use')
    parser.add_argument('--reset-jobs', action='store_true', help='reset all jobs of the simulation')

    args = parser.parse_args()

    run_matching(args.sim_id, args.place_name, args.num_threads, args.reset_jobs)
