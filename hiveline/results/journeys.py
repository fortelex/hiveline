import datetime
import json
import math
import os.path
from typing import Callable, Generator

from hiveline.mongo.db import get_database
from hiveline.routing import fptf
from hiveline.routing.util import ensure_directory

rail_modes = [fptf.Mode.TRAIN, fptf.Mode.BUS, fptf.Mode.GONDOLA, fptf.Mode.WATERCRAFT]


class Option:
    def __init__(self, result):
        self.id = result["route-option-id"]
        self.origin = fptf.Location(longitude=result["origin"][0], latitude=result["origin"][1])
        self.destination = fptf.Location(longitude=result["destination"][0], latitude=result["destination"][1])
        self.departure = fptf.read_datetime(result["departure"])
        self.modes = [fptf.Mode.from_string(m) for m in result["modes"]]
        self.journey = fptf.journey_from_json(result["journey"])

    def to_dict(self):
        return {
            "route-option-id": self.id,
            "origin": [self.origin.longitude, self.origin.latitude],
            "destination": [self.destination.longitude, self.destination.latitude],
            "departure": fptf.format_datetime(self.departure),
            "modes": [m.to_string() for m in self.modes],
            "journey": self.journey.to_dict()
        }

    def has_car(self):
        """
        Check if a route option has a car leg
        :param option: the route option
        :return: True if the route option has a car leg, False otherwise
        """

        for leg in self.journey.legs:
            mode = leg.mode

            if mode == fptf.Mode.CAR:
                return True

        return False


class Vehicles:
    def __init__(self, result):
        self.car = result["car"]
        self.moto = result["moto"]
        self.utilities = result["utilities"]
        self.usage = result["usage"]

    def to_dict(self):
        return {
            "car": self.car,
            "moto": self.moto,
            "utilities": self.utilities,
            "usage": self.usage
        }


class Traveller:
    def __init__(self, result):
        self.employed = result["employed"]
        self.employment_type = result["employment_type"] if "employment_type" in result else None
        self.vehicles = Vehicles(result["vehicles"])
        self.age = result["age"]
        self.vc_created = fptf.read_datetime(result["vc-created"])

    def to_dict(self):
        return {
            "employed": self.employed,
            "employment-type": self.employment_type,
            "vehicles": self.vehicles.to_dict(),
            "age": self.age,
            "vc-created": fptf.format_datetime(self.vc_created)
        }


class Options:
    def __init__(self, result):
        self.vc_id = result["vc-id"]
        self.sim_id = result["sim-id"]
        self.created = fptf.read_datetime(result["created"])
        self.meta = result["meta"]
        self.traveller = Traveller(result["traveller"])
        self.options = [Option(o) for o in result["options"]]

    def get_option(self, option_id: str):
        for o in self.options:
            if o.id == option_id:
                return o
        return None

    def to_dict(self):
        return {
            "vc-id": self.vc_id,
            "sim-id": self.sim_id,
            "created": fptf.format_datetime(self.created),
            "meta": self.meta,
            "traveller": self.traveller.to_dict(),
            "options": [o.to_dict() for o in self.options]
        }


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

        car_share = car_pm / total_pm
        rail_share = rail_pm / total_pm
        bus_share = bus_pm / total_pm
        walk_share = walk_pm / total_pm

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


def __approx_dist(origin: fptf.Location, destination: fptf.Location):
    """
    Approximate the distance between two points in meters using the Haversine formula.

    :param origin: object with fields lon, lat
    :param destination: object with fields lon, lat
    :return: distance in meters
    """

    # Convert latitude and longitude from degrees to radians
    lon1 = math.radians(origin.longitude)
    lat1 = math.radians(origin.latitude)
    lon2 = math.radians(destination.longitude)
    lat2 = math.radians(destination.latitude)

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


def __get_distance(leg: fptf.Leg) -> float:
    if not leg.stopovers:
        return __approx_dist(fptf.get_location(leg.origin), fptf.get_location(leg.destination))

    stopover_locations = [fptf.get_location(stopover.stop) for stopover in leg.stopovers]
    stopover_locations = [loc for loc in stopover_locations if loc is not None]

    distances = [__approx_dist(stopover_locations[i], stopover_locations[i + 1]) for i in
                 range(len(stopover_locations) - 1)]

    return sum(distances)


def get_option_stats(option: Option) -> JourneyStats:
    return get_journey_stats(option.journey)


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
