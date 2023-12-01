from datetime import datetime

import numpy as np
import requests

from mongo import get_database


def get_route(from_lat, from_lon, to_lat, to_lon, date, time, is_arrival=False, modes=None, client_timeout=40):
    """
    This function queries the OTP GraphQL endpoint and returns the itineraries

    :param from_lat: latitude of the starting point
    :param from_lon: longitude of the starting point
    :param to_lat: latitude of the destination
    :param to_lon: longitude of the destination
    :param date: date of the trip
    :param time: time of the trip
    :param is_arrival: whether the time is the arrival time or the departure time
    :param modes: list of modes to use for the trip (e.g. ["WALK", "TRANSIT"])
    :param client_timeout: timeout for the request

    :return: list of itineraries
    """
    if modes is None:
        modes = ["WALK", "TRANSIT"]

    url = "http://localhost:8080/otp/routers/default/index/graphql"

    mode_str = '{mode: ' + '} {mode:'.join(modes) + '}'

    is_arrival_str = "true" if is_arrival else "false"

    query = """
    {
        plan(
            from: { lat:%s,lon:%s}
            to: {lat:%s,lon:%s}
            date: "%s"
            time: "%s"
            arriveBy: %s
          
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
                    legGeometry {
                        points
                    }
                }
            }
        }
    }
    """ % (from_lat, from_lon, to_lat, to_lon, date, time, is_arrival_str, mode_str)

    headers = {
        'Content-Type': 'application/json'
    }

    # Send the request to the OTP GraphQL endpoint
    response = requests.post(url, json={'query': query}, headers=headers, timeout=client_timeout)

    # Check if the request was successful
    if response.status_code == 200:
        json_data = response.json()

        if "data" not in json_data:
            print("Empty data key. OTP may have failed to parse the request. Query:")
            print(query)
            print("Response:")
            print(json_data)

            return None

        itineraries = json_data['data']['plan']['itineraries']

        # Return the itineraries
        return itineraries
    else:
        print("Error querying OpenTripPlanner:", response.status_code)
        print(response.json())

        return None


# This dictionary stores the delay data for each operator
delay_data = {}


def __read_delay_statistics():
    """
    This function reads the delay statistics from the database

    :param path: path to the delay files
    """
    db = get_database()

    coll = db["delay-statistics"]

    for doc in coll.find():
        name = doc["name"]
        starts = doc["starts"]
        weights = doc["weights"]
        substituted_percent = doc["substituted_percent"]
        cancelled_percent = doc["cancelled_percent"]

        identity = list(range(len(starts)))

        delay_data[name] = {
            "starts": starts,
            "weights": weights,
            "substituted_percent": substituted_percent,
            "cancelled_percent": cancelled_percent,
            "identity": identity
        }


def __ensure_delay_statistics():
    """
    This function ensures that the delay statistics are loaded. If they are not loaded, they are loaded from the
    database.

    :return: None
    """
    if len(delay_data) == 0:
        __read_delay_statistics()


def __get_random_delay(operator_name):
    """
    This function returns a random delay for the specified operator. The delay is either cancelled or a random value
    between the specified interval.

    :param operator_name: the name of the operator
    :return: a dictionary with the keys "cancelled" and "delay"
    """
    __ensure_delay_statistics()

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


def get_delayed_route(from_lat, from_lon, to_lat, to_lon, date, time, is_arrival, modes, client_timeout=40):
    """
    This function returns a delayed itinerary for the specified parameters. It uses the fastest itinerary from OTP and
    adds a random delay to each leg of the itinerary. If a leg is cancelled or the traveller cannot catch the next
    connection, OTP may be queried multiple times.

    :param from_lat: latitude of the start location
    :param from_lon: longitude of the start location
    :param to_lat: latitude of the destination
    :param to_lon: longitude of the destination
    :param date: date of the trip in the format YYYY-MM-DD
    :param time: time of the trip in the format HH:MM:SS
    :param is_arrival: whether the time is the arrival time or the departure time
    :param modes: list of modes to use for the trip (e.g. ["WALK", "TRANSIT"])
    :param client_timeout: timeout for the OTP request
    :return: a delayed itinerary
    """
    __ensure_delay_statistics()

    itineraries = get_route(from_lat, from_lon, to_lat, to_lon, date, time, is_arrival, modes, client_timeout)

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
            delay = __get_random_delay(operator_name)

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

        itineraries = get_route(pos_lat, pos_lon, to_lat, to_lon, new_date, new_time, is_arrival, modes, client_timeout)
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
