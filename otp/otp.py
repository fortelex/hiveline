import math
from datetime import datetime

import numpy as np
import pandas as pd
import requests


def get_route(from_lat, from_lon, to_lat, to_lon, date, time, modes=None):
    """
    This function queries the OTP GraphQL endpoint and returns the itineraries

    :param from_lat: latitude of the starting point
    :param from_lon: longitude of the starting point
    :param to_lat: latitude of the destination
    :param to_lon: longitude of the destination
    :param date: date of the trip
    :param time: time of the trip
    :param modes: list of modes to use for the trip (e.g. ["WALK", "TRANSIT"])

    :return: list of itineraries
    """
    if modes is None:
        modes = ["WALK", "TRANSIT"]

    url = "http://localhost:8080/otp/routers/default/index/graphql"

    mode_str = '{mode: ' + '} {mode:'.join(modes) + '}'

    query = """
    {
        plan(
            from: { lat:%s,lon:%s}
            to: {lat:%s,lon:%s}
            date: "%s"
            time: "%s"
          
            transportModes: [%s]) {
            itineraries {
                startTime
                endTime
                legs {
                    mode
                    startTime
                    endTime
                    from {
                        name
                        lat
                        lon
                        departureTime
                        arrivalTime
                    }
                    to {
                        name
                        lat
                        lon
                        departureTime
                        arrivalTime
                    }
                    route {
                        gtfsId
                        longName
                        shortName
                        agency {
                            id
                            name
                            gtfsId
                        }
                    }
                    steps {
                      distance
                      streetName
                      relativeDirection
                      absoluteDirection
                      stayOn
                      area
                      bogusName
                      lon
                      lat
                    }
                }
            }
        }
    }
    """ % (from_lat, from_lon, to_lat, to_lon, date, time, mode_str)

    headers = {
        'Content-Type': 'application/json'
    }

    # Send the request to the OTP GraphQL endpoint
    response = requests.post(url, json={'query': query}, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        json_data = response.json()

        itineraries = json_data['data']['plan']['itineraries']

        # Return the itineraries
        return itineraries
    else:
        print("Error querying OpenTripPlanner:", response.status_code)
        print(response.json())

        return None


# This dictionary stores the delay data for each operator
delay_data = {}


def read_delay_file(path):
    """
    This function reads the delay files from the specified path and stores the data in the delay_data dictionary

    :param path: path to the delay files
    """
    df = pd.read_csv(path, sep=",")

    data = {}

    for index, row in df.iterrows():
        agency = row["agency"].lower()

        if agency not in data:
            data[agency] = {"bins": [], "substituted_percent": 0, "cancelled_percent": 0}

        label = row["label"]
        weight = float(str(row["percent"]).rstrip("%"))

        if math.isnan(weight):
            weight = 0

        if label == "substituted":
            data[agency]["substituted_percent"] = weight
            continue

        if label == "cancelled":
            data[agency]["cancelled_percent"] = weight
            continue

        bin_start = int(label.rstrip("–"))
        data[agency]["bins"] += [(bin_start, weight)]

    for agency in data:
        bins = data[agency]["bins"]
        bins = np.sort(np.array(bins, dtype=[("start", int), ("weight", float)]), order="start")

        starts = [x[0] for x in bins]
        identity = np.arange(len(starts))
        weights = [x[1] for x in bins]

        # normalize weights
        weight_sum = sum(weights)
        weights = np.array([x / weight_sum for x in weights])

        delay_data[agency] = {
            "starts": starts,
            "identity": identity,
            "weights": weights,
            "substituted_percent": data[agency]["substituted_percent"],
            "cancelled_percent": data[agency]["cancelled_percent"]
        }


def get_random_delay(operator_name):
    """
    This function returns a random delay for the specified operator. The delay is either cancelled or a random value
    between the specified interval.

    Make sure to call read_delay_files before calling this function.

    :param operator_name: the name of the operator
    :return: a dictionary with the keys "cancelled" and "delay"
    """
    operator_name = operator_name.lower()
    if operator_name not in delay_data:
        operator_name = "average"

    cancelled_percent = delay_data[operator_name]["cancelled_percent"]

    if np.random.random() * 100 < cancelled_percent:
        return {
            "cancelled": True
        }

    starts = delay_data[operator_name]["starts"]
    identity = delay_data[operator_name]["identity"]
    weights = delay_data[operator_name]["weights"]

    key = np.random.choice(identity, p=weights)
    interval_start = starts[key]
    interval_end = interval_start + 5
    if key < len(starts) - 1:
        interval_end = starts[key + 1]

    val = np.random.randint(interval_start, interval_end)

    return {
        "cancelled": False,
        "delay": val
    }


time_dependent_modes = ["BUS", "CABLE_CAR", "COACH", "FERRY", "FUNICULAR", "GONDOLA", "MONORAIL", "RAIL", "SUBWAY",
                        "TRAM", "TROLLEYBUS", "TRANSIT"]


def get_delayed_route(from_lat, from_lon, to_lat, to_lon, date, time, modes):
    """
    This function returns a delayed itinerary for the specified parameters. It uses the fastest itinerary from OTP and
    adds a random delay to each leg of the itinerary. If a leg is cancelled or the traveller cannot catch the next
    connection, OTP may be queried multiple times.

    Make sure to call read_delay_files before calling this function.

    :param from_lat: latitude of the start location
    :param from_lon: longitude of the start location
    :param to_lat: latitude of the destination
    :param to_lon: longitude of the destination
    :param date: date of the trip in the format YYYY-MM-DD
    :param time: time of the trip in the format HH:MM:SS
    :param modes: list of modes to use for the trip (e.g. ["WALK", "TRANSIT"])
    :return: a delayed itinerary
    """
    itineraries = get_route(from_lat, from_lon, to_lat, to_lon, date, time, modes)

    if itineraries is None or len(itineraries) == 0:
        return None

    # Get the fastest itinerary
    current_route = itineraries[0]

    result_legs = []

    max_calls = 20
    re_calc_count = 0

    for call in range(max_calls):
        steps = 0

        current_delay = 0  # in minutes

        # iterate legs
        legs = current_route["legs"]
        leg_count = len(legs)
        while steps < leg_count:
            time_independent_start = steps

            while steps < leg_count:
                leg = legs[steps]
                leg["rtStartTime"] = leg["startTime"] + current_delay * 60 * 1000
                leg["rtEndTime"] = leg["endTime"] + current_delay * 60 * 1000
                if leg["mode"] in time_dependent_modes:
                    break
                steps += 1

            if steps >= leg_count:
                # we can catch the last connection
                break

            # point in time when the traveller arrives at the station
            real_min_departure = legs[0]["startTime"]
            if steps > 0:
                real_min_departure = legs[steps - 1]["endTime"]

            # legs[steps] is a time dependent leg
            leg = current_route["legs"][steps]

            # get the operator name
            operator_name = leg["route"]["agency"]["name"]

            # get the delay
            delay = get_random_delay(operator_name)

            # check if the connection is cancelled
            if delay["cancelled"]:
                # trip is cancelled, reset the steps to the start of the time independent legs
                steps = time_independent_start
                break

            real_departure = leg["startTime"] + delay["delay"] * 60 * 1000

            if real_departure < real_min_departure:
                # we cannot catch the connection, reset the steps to the start of the time independent legs
                steps = time_independent_start
                break

            current_delay = delay["delay"]
            legs[steps]["rtStartTime"] = real_departure
            legs[steps]["rtEndTime"] = legs[steps]["endTime"] + current_delay * 60 * 1000
            steps += 1

        if steps >= leg_count:
            # we can catch the last connection
            result_legs += legs
            break

        # we cannot catch the last connection
        result_legs += legs[:steps]

        # route from the last station to the destination
        last_leg = legs[0]
        position = last_leg["from"]
        new_dep_unix = last_leg["startTime"]
        if steps > 0:
            last_leg = legs[steps - 1]
            position = last_leg["to"]
            new_dep_unix = last_leg["rtEndTime"]

        pos_lon = position["lon"]
        pos_lat = position["lat"]

        new_dep = datetime.fromtimestamp(new_dep_unix / 1000.0)
        new_date = new_dep.strftime("%Y-%m-%d")
        new_time = new_dep.strftime("%H:%M")

        itineraries = get_route(pos_lat, pos_lon, to_lat, to_lon, new_date, new_time, modes)
        re_calc_count += 1

        if itineraries is None or len(itineraries) == 0:
            return None

        current_route = itineraries[0]

    start_time = result_legs[0]["startTime"]
    end_time = result_legs[-1]["endTime"]
    rt_end_time = result_legs[-1]["rtEndTime"]

    return {
        "legs": result_legs,
        "startTime": start_time,
        "endTime": end_time,
        "rtEndTime": rt_end_time,
        "reCalcCount": re_calc_count
    }
