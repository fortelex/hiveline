if __name__ == "__main__":
    import os
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    sys.path.append(os.getenv("PROJECT_PATH"))

import hiveline.routing.config as config

import subprocess

import argparse

def route_virtual_commuters(sim_id, use_delays=True, force_graph_rebuild=False, graph_build_memory=4, server_memory=4,
                            num_threads=4, reset_jobs=False, reset_failed=False, api_timeout=20):
    """
    Run the routing algorithm for a virtual commuter set. It will spawn a new OTP process and run the routing algorithm
    for all open jobs in the database. It will also update the database with the results of the routing algorithm.
    :param sim_id: The virtual commuter set id
    :param use_delays: Whether to use delays or not
    :param force_graph_rebuild: Whether to force a rebuild of the graph or not
    :param graph_build_memory: The amount of memory to use for the graph build process
    :param server_memory: The amount of memory to use for the OTP server
    :param num_threads: The number of threads to use for sending route requests to the server
    :param reset_jobs: Whether to reset all jobs to pending or not
    :param reset_failed: Whether to reset all failed jobs to pending or not
    :param api_timeout: The timeout for the OTP server
    :return:
    """
    args = ["python", config.base_path + "routing/vc_router.py", str(sim_id), "--graph-build-memory",
            str(graph_build_memory),
            "--server-memory", str(server_memory), "--num-threads", str(num_threads), "--api-timeout", str(api_timeout)]

    if use_delays:
        args.append("--use-delays")

    if force_graph_rebuild:
        args.append("--force-graph-rebuild")

    if reset_jobs:
        args.append("--reset-jobs")

    if reset_failed:
        args.append("--reset-failed")

    print("[WRAPPER] Running routing algorithm for sim_id %s" % sim_id)

    try:
        # Start the process and pipe its output to the main console
        process = subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)

        # Wait for the process to complete
        process.wait()

        print("[WRAPPER] Routing algorithm for sim_id %s finished" % sim_id)

    except Exception as e:
        process.kill()
        print("[WRAPPER] Routing algorithm for sim_id %s killed" % sim_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the routing algorithm for a virtual commuter set')
    parser.add_argument('sim_id', type=str, help='Simulation id')
    parser.add_argument('--no-delays', dest='no_delays', action='store_true', help='Whether to use delays or not')
    parser.add_argument('--force-graph-rebuild', dest='force_graph_rebuild', action='store_true', help='Whether to '
                                                                                                       'force a rebuild of the graph or not')
    parser.add_argument('--graph-build-memory', dest='graph_build_memory', type=int, default=4, help='The amount of '
                                                                                                     'memory to use for the graph build process (in GB)')
    parser.add_argument('--server-memory', dest='server_memory', type=int, default=4, help='The amount of memory to '
                                                                                           'use for the OTP server (in GB)')
    parser.add_argument('--num-threads', dest='num_threads', type=int, default=4, help='The number of threads to use '
                                                                                       'for sending route requests to the server')
    parser.add_argument('--reset-jobs', dest='reset_jobs', action='store_true', help='Whether to reset all jobs for '
                                                                                     'this simulation')
    parser.add_argument('--reset-failed', dest='reset_failed', action='store_true', help='Whether to reset all failed '
                                                                                         'jobs for this simulation')
    parser.add_argument('--api-timeout', dest='api_timeout', type=int, default=20,
                        help='The timeout for the OTP server (in seconds)')

    args = parser.parse_args()

    route_virtual_commuters(args.sim_id, not args.no_delays, args.force_graph_rebuild, args.graph_build_memory,
                            args.server_memory,
                            args.num_threads,
                            args.reset_jobs, args.reset_failed, args.api_timeout)
