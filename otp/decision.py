from mongo.mongo import get_database
import vc_extract


def run_decisions(db, sim_id):
    route_options = db["route-options"]

    results = route_options.find({"sim-id": sim_id})

    total_car_meters = 0
    total_transit_meters = 0

    total_car_passengers = 0
    total_transit_passengers = 0
    total_walkers = 0

    transit_modes = ["bus", "rail", "tram", "subway"]

    car_owners_choosing_cars = 0
    car_owners_choosing_transit = 0
    car_owners_choosing_walk = 0

    for result in results:
        options = result["options"]

        has_car = vc_extract.has_motor_vehicle(result["traveller"])  # does the vc own a car?

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

        total_walkers += 1

    print(f"Total car meters: {total_car_meters}")
    print(f"Total transit meters: {total_transit_meters}")

    print(f"Total car passengers: {total_car_passengers}")
    print(f"Total transit passengers: {total_transit_passengers}")

    print(f"Total walkers: {total_walkers}")

    print(f"Car owners choosing cars: {car_owners_choosing_cars}")
    print(f"Car owners choosing transit: {car_owners_choosing_transit}")
    print(f"Car owners choosing walk: {car_owners_choosing_walk}")

    car_passenger_meters = total_car_meters * total_car_passengers
    transit_passenger_meters = total_transit_meters * total_transit_passengers

    total_passenger_meters = car_passenger_meters + transit_passenger_meters

    transit_modal_share = transit_passenger_meters / total_passenger_meters

    print(f"Transit modal share: {transit_modal_share * 100}%")


def run_congestion_decision(db, sim_id):



database = get_database()
run_decisions(database, "735a3098-8a19-4252-9ca8-9372891e90b3")
