import argparse
import threading
import time
from datetime import datetime

import bson.errors
import osmnx as ox
import pymongo.errors

import historical_osmnx
from hiveline.mongo.db import get_database


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
                "matched_docs": {
                    "$not": {
                        "$elemMatch": {
                            "sim-id": sim_id
                        }
                    }
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


def __process_route_result(route_results_coll, route_result, graph):
    """
    Run matching algorithm for a single route result.
    :param route_results_coll: The collection to update the route result in
    :param route_result: The route result to process
    :param graph: The undirected graph to use for the matching
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

                routes = ox.shortest_path(graph, origins, destinations, weight='length')

                first = routes[0][0]
                route = [first] + [item for sublist in routes for item in sublist[1:]]

                leg["osm_nodes"] = route

                has_changed = True

    if not has_changed:
        return

    route_results_coll.replace_one({"_id": route_result["_id"]}, route_result)


def __iterate_jobs(db, sim_id, graph, debug=False, progress_fac=1):
    """
    Iterate over all matching jobs and run the matching algorithm for each job.
    :param db: the database
    :param sim_id: the simulation id
    :param graph: the undirected graph to use for the matching
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
            __process_route_result(route_results_coll, route_result, graph)

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


def __spawn_job_pull_threads(db, sim_id, graph, num_threads=4):
    """
    Spawn threads to pull jobs from the database and run the matching algorithm for each job.
    :param db: the database
    :param sim_id: the simulation id
    :param graph: the undirected graph to use for the matching
    :param num_threads: the number of threads to spawn
    :return:
    """
    threads = []

    for i in range(num_threads):
        t = threading.Thread(target=__iterate_jobs, args=(db, sim_id, graph, i == 0, num_threads))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


def __find_results_with_osm_nodes(db, sim_id):
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


def __get_edge_set(db, sim_id):
    results = __find_results_with_osm_nodes(db, sim_id)

    edge_set = set()

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

                for route in iti_routes:
                    for i in range(len(route) - 1):
                        edge = (route[i], route[i + 1])
                        edge_set.add(edge)

                found_car_route = True
                break

            if found_car_route:
                break

    return edge_set


def __dump_metadata(coll, to_dump):
    """
    Dumps metadata to the database. If the metadata already exists, it will not be dumped again.
    :param coll: the collection to dump to
    :param to_dump: the metadata to dump
    :return:
    """
    try:
        coll.insert_one(to_dump)
    except pymongo.errors.DuplicateKeyError:
        pass
    except bson.errors.InvalidDocument as e:
        print("Invalid document: " + str(to_dump))
        print(e)

        for key in to_dump.keys():
            print(f"{key}: {to_dump[key]}, type: {type(to_dump[key])}")


def __dump_used_edge_metadata(db, sim_id, edge_set, graph):
    """
    Dumps metadata for the edges that are used in the simulation.
    :param db: The database
    :param sim_id: The simulation id
    :param edge_set: The set of edges that are used in the simulation
    :param graph: An undirected graph
    :return:
    """
    edge_count = len(edge_set)
    print("Dumping {} edges".format(edge_count))

    sim = db["simulations"].find_one({"sim-id": sim_id})

    pivot_date = sim["pivot-date"]
    pivot_date_str = pivot_date.isoformat()

    edge_data_coll = db["street-edge-data"]

    progress = 0
    last_print = 0

    for edge in edge_set:
        progress += 1

        if time.time() - last_print > 1:
            print("Progress: {:.2f}%".format(progress / edge_count * 100))
            last_print = time.time()

        origin = edge[0]
        destination = edge[1]

        if origin > destination:
            origin, destination = destination, origin

        edge_id = str(origin) + "-" + str(destination) + "-" + pivot_date_str
        edge = graph.edges[origin, destination, 0].copy()

        if "geometry" in edge:
            del edge["geometry"]

        edge_data = {
            "edge-id": edge_id,
            "edge": edge
        }

        __dump_metadata(edge_data_coll, edge_data)


def __dump_used_node_metadata(db, sim_id, edge_set, graph):
    """
    Dumps metadata for the nodes that are used in the simulation.
    :param db: The database
    :param sim_id: The simulation id
    :param edge_set: The set of edges that are used in the simulation
    :param graph: An undirected graph
    :return:
    """
    node_set = set()

    for edge in edge_set:
        node_set.add(edge[0])
        node_set.add(edge[1])

    node_count = len(node_set)
    print("Dumping {} nodes".format(node_count))

    sim = db["simulations"].find_one({"sim-id": sim_id})

    pivot_date = sim["pivot-date"]
    pivot_date_str = pivot_date.isoformat()

    node_data_coll = db["street-node-data"]

    progress = 0
    last_print = 0

    for node in node_set:
        progress += 1

        if time.time() - last_print > 1:
            print("Progress: {:.2f}%".format(progress / node_count * 100))
            last_print = time.time()

        node_id = str(node) + "-" + pivot_date_str
        node_data = {
            "node-id": node_id,
            "node": graph.nodes[node].copy()
        }

        __dump_metadata(node_data_coll, node_data)


def run_matching(sim_id, place_name=None, num_threads=4, reset_jobs=False, recalc_edge_data=False,
                 recalc_node_data=False):
    """
    Run the matching algorithm for the given simulation id.
    :param sim_id: the simulation id
    :param place_name: the place name
    :param num_threads: the number of threads to use
    :param reset_jobs: if True, reset all jobs of the simulation
    :param recalc_edge_data: if True, force recalculate the edge metadata in case there are no active jobs
    :param recalc_node_data: if True, force recalculate the node metadata in case there are no active jobs
    :return:
    """
    db = get_database()

    __create_matching_jobs(db, sim_id)
    if reset_jobs:
        __reset_jobs(db, sim_id)

    if __no_active_jobs(db, sim_id):
        if recalc_edge_data or recalc_node_data:
            print("No active jobs, skipping matching algorithm. Recalculating edge metadata...")
            graph = historical_osmnx.get_graph(db, sim_id, place_name, undirected=True)
            print("Dumping used edge/node metadata")
            t = time.time()
            edge_set = __get_edge_set(db, sim_id)

            if recalc_node_data:
                __dump_used_node_metadata(db, sim_id, edge_set, graph)
            if recalc_edge_data:
                __dump_used_edge_metadata(db, sim_id, edge_set, graph)
            print("Dumping finished in {:.2f} seconds".format(time.time() - t))
            return

        print(
            "No active jobs, exiting. Use --reset-jobs to reset all jobs. Use --recalc-edge-data to recalculate edge metadata for finished jobs.")
        return

    graph = historical_osmnx.get_graph(db, sim_id, place_name, undirected=True)

    print("Graph loaded.")

    t = time.time()
    __spawn_job_pull_threads(db, sim_id, graph, num_threads=num_threads)
    print("Matching algorithm finished in {:.2f} seconds".format(time.time() - t))

    print("Dumping used node and edge metadata")
    t = time.time()
    edge_set = __get_edge_set(db, sim_id)

    __dump_used_node_metadata(db, sim_id, edge_set, graph)
    __dump_used_edge_metadata(db, sim_id, edge_set, graph)
    print("Dumping finished in {:.2f} seconds".format(time.time() - t))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the matching algorithm for the given simulation id.')
    parser.add_argument('sim_id', type=str, help='the simulation id')
    parser.add_argument('--place-name', type=str,
                        help='the place name. If not provided, the place name will fallback to the one in the database')
    parser.add_argument('--num-threads', type=int, default=4, help='the number of threads to use')
    parser.add_argument('--reset-jobs', action='store_true', help='reset all jobs of the simulation')
    parser.add_argument('--recalc-edge-data', action='store_true', help='recalculate edge metadata for finished jobs')
    parser.add_argument('--recalc-node-data', action='store_true', help='recalculate node metadata for finished jobs')

    args = parser.parse_args()

    run_matching(args.sim_id, args.place_name, args.num_threads, args.reset_jobs, args.recalc_edge_data,
                 args.recalc_node_data)
