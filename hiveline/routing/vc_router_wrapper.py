import argparse
import os
import subprocess

from dotenv import load_dotenv

load_dotenv()


def route_virtual_commuters(sim_id, profile="opentripplanner", data_dir="./cache", use_delays=True,
                            force_graph_rebuild=False, memory_gb=4, num_threads=4,
                            reset_jobs=False, reset_failed=False, timeout=20):
    """
    Run the routing algorithm for a virtual commuter set. It will spawn a new OTP process and run the routing algorithm
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
    base_path = os.getenv("PROJECT_PATH")
    if base_path.endswith("/"):
        base_path = base_path[:-1]

    args = ["python", base_path + "/hiveline/routing/vc_router.py", str(sim_id), "--profile", profile, "--data-dir",
            data_dir, "--memory", str(memory_gb), "--num-threads", str(num_threads), "--timeout", str(timeout)]

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
    parser.add_argument("--profile", dest="profile", type=str, default="opentripplanner",
                        help="The profile to use for the routing server and client (opentripplanner, bifrost, ...)")
    parser.add_argument("--data-dir", dest="data_dir", type=str, default="./cache",
                        help="The directory where the data should be stored")
    parser.add_argument('--no-delays', dest='no_delays', action='store_true', help='Whether to use delays or not')
    parser.add_argument('--force-graph-rebuild', dest='force_graph_rebuild', action='store_true', help='Whether to '
                                                                                                       'force a rebuild of the graph or not')
    parser.add_argument('--memory', dest='memory_gb', type=int, default=4, help='The amount of memory to '
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

    route_virtual_commuters(args.sim_id, args.profile, args.data_dir, not args.no_delays, args.force_graph_rebuild,
                            args.memory_gb, args.num_threads, args.reset_jobs, args.reset_failed, args.timeout)
