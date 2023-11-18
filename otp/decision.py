from mongo.mongo import get_database


def run_decisions(db, sim_id):
    route_options = db["route-options"]

    results = route_options.find({"sim-id": sim_id})

    total_car_meters = 0
    total_transit_meters = 0

    transit_modes = ["bus", "rail", "tram", "subway"]

    for result in results:
        options = result["options"]

        # choose the fastest option
        fastest_option = None

        for option in options:
            if option is None:
                continue

            if fastest_option is None:
                fastest_option = option
                continue

            if option["route-duration"] < fastest_option["route-duration"]:
                fastest_option = option

        if fastest_option is None:
            continue

        legs = fastest_option["modes"]

        for leg in legs:
            mode = leg["mode"]

            if mode == "car":
                total_car_meters += leg["distance"]
                continue

            if mode in transit_modes:
                total_transit_meters += leg["distance"]
                continue

            if mode == "bicycle":
                continue

            if mode == "walk":
                continue

            print(f"Unknown mode: {mode}")

    print(f"Total car meters: {total_car_meters}")
    print(f"Total transit meters: {total_transit_meters}")

    transit_modal_share = total_transit_meters / (total_car_meters + total_transit_meters)

    print(f"Transit modal share: {transit_modal_share * 100}%")


database = get_database()
run_decisions(database, "735a3098-8a19-4252-9ca8-9372891e90b3")
