import datetime

from hiveline.models import fptf


class Option:
    def __init__(self, id: str, origin: fptf.Location, destination: fptf.Location, departure: datetime.datetime,
                 modes: list[fptf.Mode], journey: fptf.Journey,
                 trace: list[tuple[tuple[float, float], datetime.datetime, fptf.Mode, bool]] | None = None):
        self.id = id
        self.origin = origin
        self.destination = destination
        self.departure = departure
        self.modes = modes
        self.journey = journey
        self.trace = trace

    def to_dict(self):
        return {
            "route-option-id": self.id,
            "origin": [self.origin.longitude, self.origin.latitude],
            "destination": [self.destination.longitude, self.destination.latitude],
            "departure": fptf.format_datetime(self.departure),
            "modes": [m.to_string() for m in self.modes],
            "journey": self.journey.to_dict()
        }

    @staticmethod
    def from_dict(result):
        id = result["route-option-id"]
        origin = fptf.Location(longitude=result["origin"][0], latitude=result["origin"][1])
        destination = fptf.Location(longitude=result["destination"][0], latitude=result["destination"][1])
        departure = fptf.read_datetime(result["departure"])
        modes = [fptf.Mode.from_string(m) for m in result["modes"]]
        journey = fptf.journey_from_json(result["journey"])
        trace = None
        return Option(id, origin, destination, departure, modes, journey, trace)

    def has_car(self):
        """
        Check if a route option has a car leg
        :return: True if the route option has a car leg, False otherwise
        """

        for leg in self.journey.legs:
            mode = leg.mode

            if mode == fptf.Mode.CAR:
                return True

        return False

    def get_trace(self) -> list[tuple[tuple[float, float], datetime.datetime, fptf.Mode, bool]]:
        if self.trace is None:
            self.trace = self.journey.get_trace()
        return self.trace


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
        self.options = [Option.from_dict(o) for o in result["options"]]

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
