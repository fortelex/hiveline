import datetime
import json
import math
import os.path
from typing import Callable, Generator

from shapely import Polygon, Point

from hiveline.models import fptf
from hiveline.models.options import Options, Option
from hiveline.mongo.db import get_database
from hiveline.routing.util import ensure_directory

rail_modes = [fptf.Mode.TRAIN, fptf.Mode.GONDOLA, fptf.Mode.WATERCRAFT]


class Journeys:
    def __init__(self, sim_id: str, db=None, use_cache=True, cache="./cache"):
        if db is None:
            db = get_database()
        self.db = db
        self.sim_id = sim_id
        if cache.endswith("/"):
            cache = cache[:-1]
        self.use_cache = use_cache
        self.cache = cache + "/hiveline-journeys"
        ensure_directory(self.cache)

        self.options = self.__find_all()

    def __find_all(self):
        # check if cached
        if self.use_cache and os.path.isfile(self.cache + "/" + self.sim_id + ".json"):
            print("Found cached results")
            return self.__load_cache()

        t = datetime.datetime.now()

        results = list(self.db["route-results"].find({"sim-id": self.sim_id}))

        print(f"Found {len(results)} results in {datetime.datetime.now() - t}")
        t = datetime.datetime.now()

        options = [Options(r) for r in results]

        self.__save_cache(options)

        print(f"Converted {len(options)} results in {datetime.datetime.now() - t}")

        return options

    def iterate(self) -> Generator[Options, None, None]:
        for o in self.options:
            yield o

    def iterate_selection(self, selection: list[str | None]) -> Generator[Option, None, None]:
        for (i, sel) in enumerate(selection):
            if sel is not None:
                yield self.options[i].get_option(sel)

    def iterate_traces(self, selection=None) -> Generator[list[tuple[tuple[float, float], datetime.datetime, fptf.Mode, bool]], None, None]:
        for (i, o) in enumerate(self.options):
            if selection is not None and i >= len(selection):
                break

            opt = o.options
            if selection is not None:
                option = o.get_option(selection[i])
                if option is None:
                    continue
                opt = [option]

            for option in opt:
                yield option.get_trace()

    def get_selection(self, decision: Callable[[Options], Option | None], max_count=None) -> list[str | None]:
        """
        Get the selection of options based on a decision function
        :param decision: the decision function
        :param max_count: (optional) the maximum number of options to return
        :return:
        """
        options = self.options
        if max_count is not None:
            options = options[:max_count]

        decided = [decision(o) for o in options]
        return [o.id if o is not None else None for o in decided]

    def __load_cache(self):
        with open(self.cache + "/" + self.sim_id + ".json", "r") as f:
            return [Options(o) for o in json.load(f)]

    def __save_cache(self, options: list[Options]):
        with open(self.cache + "/" + self.sim_id + ".json", "w") as f:
            json.dump([o.to_dict() for o in options], f)

    def prepare_traces(self):
        """
        Prepare the traces for all options
        :return:
        """
        for o in self.options:
            for option in o.options:
                option.get_trace()


class JourneyStats:
    def __init__(self):
        self.car_meters = 0
        self.rail_meters = 0
        self.bus_meters = 0
        self.walk_meters = 0

        self.car_passengers = 0
        self.rail_passengers = 0
        self.bus_passengers = 0
        self.walkers = 0

    def to_dict(self):
        return {
            "car_meters": self.car_meters,
            "rail_meters": self.rail_meters,
            "bus_meters": self.bus_meters,
            "walk_meters": self.walk_meters,
            "car_passengers": self.car_passengers,
            "rail_passengers": self.rail_passengers,
            "bus_passengers": self.bus_passengers,
            "walkers": self.walkers
        }

    def get_all_modal_shares(self):
        """
        Get the modal shares for all modes (distance travelled in mode x people using the mode)
        :return:
        """
        car_pm = self.car_meters * self.car_passengers
        rail_pm = self.rail_meters * self.rail_passengers
        bus_pm = self.bus_meters * self.bus_passengers
        walk_pm = self.walk_meters * self.walkers

        total_pm = car_pm + rail_pm + bus_pm + walk_pm

        car_share = car_pm / total_pm if total_pm > 0 else 0
        rail_share = rail_pm / total_pm if total_pm > 0 else 0
        bus_share = bus_pm / total_pm if total_pm > 0 else 0
        walk_share = walk_pm / total_pm if total_pm > 0 else 0

        return {
            "car_share": car_share,
            "rail_share": rail_share,
            "bus_share": bus_share,
            "walk_share": walk_share,
        }

    def get_transit_modal_share(self):
        """
        Get the transit modal share according to UPPER definition from the stats
        :return: the transit modal share
        """
        total_car_meters = self.car_meters
        total_transit_meters = self.rail_meters + self.bus_meters

        total_car_passengers = self.car_passengers
        total_transit_passengers = self.rail_passengers + self.bus_passengers

        car_passenger_meters = total_car_meters * total_car_passengers
        transit_passenger_meters = total_transit_meters * total_transit_passengers

        total_passenger_meters = car_passenger_meters + transit_passenger_meters

        if total_passenger_meters == 0:
            return 0

        return transit_passenger_meters / total_passenger_meters


def __approx_dist(origin: tuple[float, float], destination: tuple[float, float]):
    """
    Approximate the distance between two points in meters using the Haversine formula.

    :param origin: object with fields lon, lat
    :param destination: object with fields lon, lat
    :return: distance in meters
    """

    # Convert latitude and longitude from degrees to radians
    lon1 = math.radians(origin[0])
    lat1 = math.radians(origin[1])
    lon2 = math.radians(destination[0])
    lat2 = math.radians(destination[1])

    # Radius of the Earth in kilometers
    r = 6371.0

    # Difference in coordinates
    d_lon = lon2 - lon1
    d_lat = lat2 - lat1

    # Haversine formula
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in kilometers
    distance_km = r * c

    # Convert to meters
    distance_meters = distance_km * 1000

    return distance_meters


def get_option_stats(option: Option, shape: Polygon | None = None) -> JourneyStats:
    trace = option.get_trace()

    if shape is not None:
        trace = filter_trace(trace, shape)

    return get_trace_stats(trace)


def filter_trace(trace: list[tuple[tuple[float, float], datetime.datetime, fptf.Mode, bool]], polygon: Polygon):
    """
    Filter a trace to only include points within a polygon
    :param trace: the trace
    :param polygon: the polygon
    :return: the filtered trace
    """
    contains = [polygon.contains(Point(t[0])) for t in trace]

    result = []

    carry_leg_start = False

    for i in range(len(trace)):
        cont = contains[i]
        point, time, mode, is_leg_start = trace[i]

        if cont:
            is_leg_start |= carry_leg_start
            carry_leg_start = False
            result.append((point, time, mode, is_leg_start))
            continue

        if is_leg_start:
            carry_leg_start = True
            continue

    return result


def get_trace_stats(trace: list[tuple[tuple[float, float], datetime.datetime, fptf.Mode, bool]]) -> JourneyStats:
    """
    Get the stats for a journey
    :param trace: the trace
    :return: the stats
    """
    stats = JourneyStats()

    for (i, (from_point, _, from_mode, is_leg_start)) in enumerate(trace[:-1]):
        to_point, _, to_mode, _ = trace[i + 1]

        if from_mode != to_mode:
            continue

        dist = __approx_dist(from_point, to_point)
        pax = 1 if is_leg_start else 0

        if from_mode == fptf.Mode.CAR:
            stats.car_meters += dist
            stats.car_passengers += pax
            continue

        if from_mode in rail_modes:
            stats.rail_meters += dist
            stats.rail_passengers += pax
            continue

        if from_mode == fptf.Mode.BUS:
            stats.bus_meters += dist
            stats.bus_passengers += pax
            continue

        if from_mode == fptf.Mode.BICYCLE:
            continue

        if from_mode == fptf.Mode.WALKING:
            stats.walk_meters += dist
            stats.walkers += pax
            continue

        print(f"Unknown mode: {from_mode}")

    return stats


def __approx_dist_fptf(origin: fptf.Location, destination: fptf.Location):
    return __approx_dist((origin.longitude, origin.latitude), (destination.longitude, destination.latitude))


def __get_distance(leg: fptf.Leg) -> float:
    if not leg.stopovers:
        return __approx_dist_fptf(fptf.get_location(leg.origin), fptf.get_location(leg.destination))

    stopover_locations = [fptf.get_location(stopover.stop) for stopover in leg.stopovers]
    stopover_locations = [loc for loc in stopover_locations if loc is not None]

    distances = [__approx_dist_fptf(stopover_locations[i], stopover_locations[i + 1]) for i in
                 range(len(stopover_locations) - 1)]

    return sum(distances)


def get_journey_stats(journey: fptf.Journey) -> JourneyStats:
    """
    Get the stats for a journey
    :param journey: the journey
    :return: the stats
    """
    stats = JourneyStats()

    for leg in journey.legs:
        mode = leg.mode
        dist = __get_distance(leg)

        if mode == fptf.Mode.CAR:
            stats.car_meters += dist
            stats.car_passengers += 1
            continue

        if mode in rail_modes:
            stats.rail_meters += dist
            stats.rail_passengers += 1
            continue

        if mode == fptf.Mode.BUS:
            stats.bus_meters += dist
            stats.bus_passengers += 1
            continue

        if mode == fptf.Mode.BICYCLE:
            continue

        if mode == fptf.Mode.WALKING:
            stats.walk_meters += dist
            stats.walkers += 1
            continue

        print(f"Unknown mode: {mode}")

    return stats
