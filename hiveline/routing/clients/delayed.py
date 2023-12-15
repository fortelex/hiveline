import datetime

import numpy as np

from hiveline.mongo.db import get_database
from hiveline.routing import fptf
from hiveline.routing.clients.routing_client import RoutingClient


def _read_delay_statistics():
    """
    This function reads the delay statistics from the database
    """
    db = get_database()

    coll = db["delay-statistics"]

    delay_data = {}

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

    return delay_data


def _get_fastest_journey(journeys):
    """
    This function returns the fastest journey from the list of journeys

    :param journeys: list of journeys
    :return: the fastest journey
    """
    durations = [journey.duration() for journey in journeys]
    min_duration = min(durations)
    min_index = durations.index(min_duration)
    return journeys[min_index]


class DelayedRoutingClient(RoutingClient):
    def __init__(self, base: RoutingClient):
        # This dictionary stores the delay data for each operator
        self.delay_data = _read_delay_statistics()
        self.base = base

    def __get_random_delay(self, operator_name):
        """
        This function returns a random delay for the specified operator. The delay is either cancelled or a random value
        between the specified interval.

        :param operator_name: the name of the operator
        :return: a dictionary with the keys "cancelled" and "delay"
        """

        operator_name = operator_name.lower()
        if operator_name not in self.delay_data:
            operator_name = "average"

        cancelled_percent = self.delay_data[operator_name]["cancelled_percent"]

        if np.random.random() * 100 < cancelled_percent:
            return {
                "cancelled": True
            }

        starts = self.delay_data[operator_name]["starts"]
        identity = self.delay_data[operator_name]["identity"]
        weights = self.delay_data[operator_name]["weights"]

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

    time_dependent_modes = [fptf.Mode.TRAIN, fptf.Mode.BUS, fptf.Mode.WATERCRAFT, fptf.Mode.AIRCRAFT, fptf.Mode.GONDOLA]

    def get_journeys(self, from_lat, from_lon, to_lat, to_lon, departure, modes):
        """
        This function returns a delayed itinerary for the specified parameters. It uses the fastest itinerary from OTP
        and adds a random delay to each leg of the itinerary. If a leg is cancelled or the traveller cannot catch the
        next connection, OTP may be queried multiple times.

        :param from_lat: latitude of the start location
        :param from_lon: longitude of the start location
        :param to_lat: latitude of the destination
        :param to_lon: longitude of the destination
        :param departure: departure time as datetime object
        :param modes: list of modes to use for the trip (e.g. ["WALK", "TRANSIT"])
        :return: a delayed journey
        """
        journey = _get_fastest_journey(self.base.get_journeys(from_lat, from_lon, to_lat, to_lon, departure, modes))

        if journey is None:
            return None

        result_legs = []

        max_calls = 20
        re_calc_count = 0

        for call in range(max_calls):
            steps = 0

            current_delay = 0  # in minutes

            # iterate legs
            leg_count = len(journey.legs)
            while steps < leg_count:
                time_independent_start = steps

                while steps < leg_count:
                    leg = journey.legs[steps]
                    leg.departure_delay = current_delay * 60
                    leg.arrival_delay = current_delay * 60
                    if leg.mode in self.time_dependent_modes:
                        break
                    steps += 1

                if steps >= leg_count:
                    # we can catch the last connection
                    break

                # point in time when the traveller arrives at the station
                real_min_departure = journey.legs[0].departure
                if steps > 0:
                    real_min_departure = journey.legs[steps - 1].arrival

                # legs[steps] is a time dependent leg
                leg = journey.legs[steps]

                # get the operator name
                operator_name = leg.operator.name

                # get the delay
                delay = self.__get_random_delay(operator_name)

                # check if the connection is cancelled
                if delay["cancelled"]:
                    # trip is cancelled, reset the steps to the start of the time independent legs
                    steps = time_independent_start
                    break

                delay_seconds = int(delay["delay"]) * 60
                real_departure = leg.departure + datetime.timedelta(seconds=delay_seconds)

                if real_departure < real_min_departure:
                    # we cannot catch the connection, reset the steps to the start of the time independent legs
                    steps = time_independent_start
                    break

                current_delay = delay["delay"]
                leg.departure_delay = delay_seconds
                leg.arrival_delay = delay_seconds
                steps += 1

            if steps >= leg_count:
                # we can catch the last connection
                result_legs += journey.legs
                break

            # we cannot catch the last connection
            result_legs += journey.legs[:steps]

            # route from the last station to the destination
            last_leg = journey.legs[0]
            position = last_leg.origin
            new_dep = last_leg.departure
            if steps > 0:
                last_leg = journey.legs[steps - 1]
                position = last_leg.destination
                new_dep = last_leg.arrival + datetime.timedelta(seconds=last_leg.arrival_delay)

            pos_lon = position.longitude
            pos_lat = position.latitude

            journey = _get_fastest_journey(self.base.get_journeys(pos_lat, pos_lon, to_lat, to_lon, new_dep, modes))
            re_calc_count += 1

            if journey is None:
                return None

        return fptf.Journey(
            id=None,
            legs=result_legs
        )
