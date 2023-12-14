import datetime
import json
from enum import Enum

supported_formats = ['%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z']  # first will be used for formatting


def _remove_empty_keys(d):
    """ Remove keys with None or empty values from a dictionary. """
    return {k: v for k, v in d.items() if v}


def _read_datetime(time_str):
    """
    Reads a time string in the RFC3339 format and returns a datetime.datetime object.
    :param time_str: The time string.
    :return: The datetime.datetime object.
    """
    if not time_str:
        return None
    for format in supported_formats:
        try:
            return datetime.datetime.strptime(time_str, format)
        except ValueError:
            pass

    print("Could not parse time string: " + time_str)
    return None


def _format_datetime(dt):
    """
    Formats a datetime.datetime object into a time string in the RFC3339 format.
    :param dt: The datetime.datetime object.
    :return: The time string.
    """
    if not dt:
        return None
    return dt.strftime(supported_formats[0])


class Location:
    """
    Represents a geographical location in the public transport system.
    It can be used by other items to indicate their locations.
    """

    def __init__(self, name=None, address=None, longitude=None, latitude=None, altitude=None):
        self.type = 'location'
        self.name = name
        self.address = address
        self.longitude = longitude
        self.latitude = latitude
        self.altitude = altitude

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'name': self.name,
            'address': self.address,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'altitude': self.altitude
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_dict(json_str):
        data = json.loads(json_str)
        return location_from_json(data)


def location_from_json(data: dict | str | None):
    """
    Creates a Location object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return Location(name=data)

    return Location(
        name=data['name'] if 'name' in data else None,
        address=data['address'] if 'address' in data else None,
        longitude=data['longitude'] if 'longitude' in data else None,
        latitude=data['latitude'] if 'latitude' in data else None,
        altitude=data['altitude'] if 'altitude' in data else None
    )


class Station:
    """
    Represents a station in the public transport system.
    A station is a larger building or area that can be identified by a name.
    """

    def __init__(self, id: str, name: str, location: Location = None, regions: list = None):
        self.type = 'station'
        self.id = id
        self.name = name
        self.location = location
        self.regions = regions or []

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'id': self.id,
            'name': self.name,
            'location': self.location.to_dict() if self.location else None,
            'regions': [r.to_dict() for r in self.regions] if self.regions else None
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return station_from_json(data)


def station_from_json(data: dict | str | None):
    """
    Creates a Station object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return Station(data, data)

    return Station(
        id=data['id'] if 'id' in data else None,
        name=data['name'] if 'name' in data else None,
        location=location_from_json(data['location']) if 'location' in data else None,
        regions=[region_from_json(r) for r in data['regions']] if 'regions' in data else None
    )


class Stop:
    """
    Represents a stop in the public transport system.
    A stop is a single small point or structure at which vehicles stop.
    """

    def __init__(self, id: str, station: Station, name: str, location: Location = None):
        self.type = 'stop'
        self.id = id
        self.station = station
        self.name = name
        self.location = location

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'id': self.id,
            'station': self.station.to_dict() if self.station else None,
            'name': self.name,
            'location': self.location.to_dict() if self.location else None
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return stop_from_json(data)


def stop_from_json(data: dict | str | None):
    """
    Creates a Stop object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return Station(data, data, location_from_json(data))

    return Stop(
        id=data['id'] if 'id' in data else None,
        station=data['station'] if 'station' in data else None,
        name=data['name'] if 'name' in data else None,
        location=location_from_json(data['location']) if 'location' in data else None
    )


def place_from_json(data: dict | str | None):
    if data is None:
        return None

    if isinstance(data, str):
        return Station(id=data, name=data)

    if 'type' not in data:
        return station_from_json(data)

    typ = data['type']
    if typ == 'location':
        return location_from_json(data)
    elif typ == 'station':
        return station_from_json(data)
    elif typ == 'stop':
        return stop_from_json(data)


def get_location(place: Location | Station | Stop) -> Location | None:
    """
    Returns the location of a place.
    :param place: The place.
    :return: The location.
    """
    if isinstance(place, Location):
        return place
    elif isinstance(place, Station):
        return place.location
    elif isinstance(place, Stop):
        if place.location:
            return place.location
        elif place.station:
            return place.station.location
    return None


class Region:
    """
    Represents a region in the public transport system.
    A region is a group of stations, like a metropolitan area.
    """

    def __init__(self, id: str, name: str, stations: list[Station] = None):
        self.type = 'region'
        self.id = id
        self.name = name
        self.stations = stations

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'id': self.id,
            'name': self.name,
            'stations': [s.to_dict() for s in self.stations] if self.stations else None
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return region_from_json(data)


def region_from_json(data: dict | str | None):
    """
    Creates a Region object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return Region(data, data)

    return Region(
        id=data['id'] if 'id' in data else None,
        name=data['name'] if 'name' in data else None,
        stations=[station_from_json(s) for s in data['stations']] if 'stations' in data else None
    )


class Mode(Enum):
    """
    Represents a mode of transport in the public transport system.
    """

    TRAIN = 'train'
    BUS = 'bus'
    WATERCRAFT = 'watercraft'
    TAXI = 'taxi'
    GONDOLA = 'gondola'
    AIRCRAFT = 'aircraft'
    CAR = 'car'
    BICYCLE = 'bicycle'
    WALKING = 'walking'
    UNKNOWN = ''

    def __init__(self, mode: str):
        self.mode = mode

    def __str__(self):
        return self.mode

    def __repr__(self):
        return self.mode

    def to_string(self):
        return self.mode

    def to_json(self):
        return json.dumps(self.mode)

    @staticmethod
    def from_string(mode):
        if mode == 'train':
            return Mode.TRAIN
        elif mode == 'bus':
            return Mode.BUS
        elif mode == 'watercraft':
            return Mode.WATERCRAFT
        elif mode == 'taxi':
            return Mode.TAXI
        elif mode == 'gondola':
            return Mode.GONDOLA
        elif mode == 'aircraft':
            return Mode.AIRCRAFT
        elif mode == 'car':
            return Mode.CAR
        elif mode == 'bicycle':
            return Mode.BICYCLE
        elif mode == 'walking':
            return Mode.WALKING
        return Mode.UNKNOWN


class Operator:
    """
    Represents an operator in the public transport system.
    An operator is an agency or company that runs public transport services.
    """

    def __init__(self, id: str, name: str):
        self.type = 'operator'
        self.id = id
        self.name = name

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'id': self.id,
            'name': self.name
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return operator_from_json(data)


def operator_from_json(data: dict | str | None):
    """
    Creates an Operator object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return Operator(data, data)

    return Operator(
        id=data['id'] if 'id' in data else None,
        name=data['name'] if 'name' in data else None
    )


class Line:
    """
    Represents a line in the public transport system.
    A line is a set of routes operated by a public transport agency.
    """

    def __init__(self, id: str, name: str, mode: Mode, routes: list, operator: Operator = None, sub_mode: str = None):
        self.type = 'line'
        self.id = id
        self.name = name
        self.mode = mode
        self.sub_mode = sub_mode
        self.routes = routes
        self.operator = operator

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'id': self.id,
            'name': self.name,
            'mode': self.mode.to_string(),
            'subMode': self.sub_mode,
            'routes': [r.to_dict() for r in self.routes] if self.routes else None,
            'operator': self.operator.to_dict() if self.operator else None
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return line_from_json(data)


def line_from_json(data: dict | str | None):
    """
    Creates a Line object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return Line(data, data, Mode.UNKNOWN, [], None)

    return Line(
        id=data['id'] if 'id' in data else None,
        name=data['name'] if 'name' in data else None,
        mode=Mode.from_string(data['mode']) if 'mode' in data else None,
        sub_mode=data['subMode'] if 'subMode' in data else None,
        routes=[route_from_json(r) for r in data['routes']] if 'routes' in data else None,
        operator=operator_from_json(data['operator']) if 'operator' in data else None
    )


class Route:
    """
    Represents a route in the public transport system.
    A route is a set of stations served by a line.
    """

    def __init__(self, id: str, line: Line, mode: Mode, stops: list[Station | Stop | Location], sub_mode: str = None):
        self.type = 'route'
        self.id = id
        self.line = line
        self.mode = mode
        self.sub_mode = sub_mode
        self.stops = stops

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'id': self.id,
            'line': self.line.to_dict() if self.line else None,
            'mode': self.mode.to_string(),
            'subMode': self.sub_mode,
            'stops': [s.to_dict() for s in self.stops] if self.stops else None
        })

    def to_json(self):
        return json.dumps(self.to_dict())


def route_from_json(data: dict | str | None):
    """
    Creates a Route object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return Route(data, line_from_json(data), Mode.UNKNOWN, [])

    return Route(
        id=data['id'] if 'id' in data else None,
        line=line_from_json(data['line']) if 'line' in data else None,
        mode=Mode.from_string(data['mode']) if 'mode' in data else None,
        sub_mode=data['subMode'] if 'subMode' in data else None,
        stops=[place_from_json(s) for s in data['stops']] if 'stops' in data else None
    )


class ScheduleSequenceElement:
    """
    Represents an element in a schedule sequence.
    """

    def __init__(self, arrival: int = None, departure: int = None):
        self.arrival = arrival
        self.departure = departure

    def to_dict(self):
        return _remove_empty_keys({
            'arrival': self.arrival,
            'departure': self.departure
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return ScheduleSequenceElement(data['arrival'], data['departure'])


class Schedule:
    """
    Represents a schedule in the public transport system.
    A schedule is a timetable for a route.
    """

    def __init__(self, id: str, route: Route, mode: Mode, sequence: list[ScheduleSequenceElement], starts,
                 sub_mode=None):
        self.type = 'schedule'
        self.id = id
        self.route = route
        self.mode = mode
        self.sub_mode = sub_mode
        self.sequence = sequence
        self.starts = starts

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'id': self.id,
            'route': self.route.to_dict() if self.route else None,
            'mode': self.mode.to_string(),
            'subMode': self.sub_mode,
            'sequence': [s.to_dict() for s in self.sequence] if self.sequence else None,
            'starts': self.starts
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return schedule_from_json(data)


def schedule_from_json(data: dict | str | None):
    """
    Creates a Schedule object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None
    if isinstance(data, str):
        return Schedule(data, route_from_json(data), Mode.UNKNOWN, [], None)
    return Schedule(
        id=data['id'] if 'id' in data else None,
        route=route_from_json(data['route']) if 'route' in data else None,
        mode=Mode.from_string(data['mode']) if 'mode' in data else None,
        sub_mode=data['subMode'] if 'subMode' in data else None,
        sequence=[ScheduleSequenceElement(s['arrival'], s['departure']) for s in
                  data['sequence']] if 'sequence' in data else None,
        starts=data['starts'] if 'starts' in data else None
    )


class Stopover:
    """
    Represents a stopover in the public transport system.
    A stopover is when a vehicle stops at a station or stop.
    """

    def __init__(self, stop: Stop | Station | Location, arrival: datetime.datetime = None, arrival_delay: int = None,
                 arrival_platform: str = None,
                 departure: datetime.datetime = None, departure_delay: int = None, departure_platform: str = None):
        self.type = 'stopover'
        self.stop = stop
        self.arrival = arrival
        self.arrival_delay = arrival_delay
        self.arrival_platform = arrival_platform
        self.departure = departure
        self.departure_delay = departure_delay
        self.departure_platform = departure_platform

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'stop': self.stop.to_dict() if self.stop else None,
            'arrival': _format_datetime(self.arrival) if self.arrival else None,
            'arrivalDelay': self.arrival_delay,
            'arrivalPlatform': self.arrival_platform,
            'departure': _format_datetime(self.departure) if self.departure else None,
            'departureDelay': self.departure_delay,
            'departurePlatform': self.departure_platform
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return stopover_from_json(data)


def stopover_from_json(data: dict | str | None):
    """
    Creates a Stopover object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return Stopover(stop=Station(data, data))

    return Stopover(
        stop=stop_from_json(data['stop']) if 'stop' in data else None,
        arrival=_read_datetime(data['arrival']) if 'arrival' in data else None,
        arrival_delay=data['arrivalDelay'] if 'arrivalDelay' in data else None,
        arrival_platform=data['arrivalPlatform'] if 'arrivalPlatform' in data else None,
        departure=_read_datetime(data['departure']) if 'departure' in data else None,
        departure_delay=data['departureDelay'] if 'departureDelay' in data else None,
        departure_platform=data['departurePlatform'] if 'departurePlatform' in data else None
    )


class Price:
    """
    Represents a price in the public transport system.
    A price is the cost of a journey or leg.

    Attributes:
        amount (float): The price in the smallest currency unit.
        currency (str): The currency code.
    """

    def __init__(self, amount: float, currency: str):
        self.amount = amount
        self.currency = currency

    def to_dict(self):
        return _remove_empty_keys({
            'amount': self.amount,
            'currency': self.currency
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return price_from_json(data)


def price_from_json(data: dict | str | None):
    """
    Creates a Price object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    return Price(
        amount=data['amount'] if 'amount' in data else None,
        currency=data['currency'] if 'currency' in data else None
    )


class Leg:
    """
    Represents a leg of a journey in the public transport system.
    A leg is a single segment of a journey, typically involving travel on a single mode of transport.

    Attributes:
        origin (str or Location): The starting point of the leg.
        destination (str or Location): The endpoint of the leg.
        departure (str): The ISO 8601 departure time string with timezone.
        departure_delay (int): Delay in seconds relative to scheduled departure.
        departure_platform (str): The platform from which the departure occurs.
        arrival (str): The ISO 8601 arrival time string with timezone.
        arrival_delay (int): Delay in seconds relative to scheduled arrival.
        arrival_platform (str): The platform at which the arrival occurs.
        stopovers (list of Stopover): Optional list of stopovers.
        schedule (str or Schedule): The schedule ID or object associated with this leg.
        mode (str): The mode of transport for this leg.
        sub_mode (str): A more specific mode of transport within the general mode category.
        public (bool): Indicates whether the leg is publicly accessible.
        operator (str or Operator): The operator ID or object for this leg.
        price (dict): Optional pricing information for the leg.
    """

    def __init__(self, origin: Stop | Station | Location, destination: Stop | Station | Location,
                 departure: datetime.datetime, arrival: datetime.datetime, mode: Mode, sub_mode: str = None,
                 departure_delay: int = None,
                 departure_platform: str = None,
                 arrival_delay: int = None, arrival_platform: str = None, line: Line = None, direction: str = None,
                 stopovers: list[Stopover] = None, schedule: Schedule = None, public: bool = True,
                 operator: Operator = None,
                 price: Price = None):
        self.type = 'leg'
        self.origin = origin
        self.destination = destination
        self.departure = departure
        self.arrival = arrival
        self.mode = mode
        self.sub_mode = sub_mode
        self.departure_delay = departure_delay
        self.departure_platform = departure_platform
        self.arrival_delay = arrival_delay
        self.arrival_platform = arrival_platform
        self.line = line
        self.direction = direction
        self.stopovers = stopovers or []
        self.schedule = schedule
        self.public = public
        self.operator = operator
        self.price = price

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'origin': self.origin.to_dict() if self.origin else None,
            'destination': self.destination.to_dict() if self.destination else None,
            'departure': _format_datetime(self.departure) if self.departure else None,
            'arrival': _format_datetime(self.arrival) if self.arrival else None,
            'mode': self.mode.to_string(),
            'subMode': self.sub_mode,
            'departureDelay': self.departure_delay,
            'departurePlatform': self.departure_platform,
            'arrivalDelay': self.arrival_delay,
            'arrivalPlatform': self.arrival_platform,
            'line': self.line.to_dict() if self.line else None,
            'direction': self.direction,
            'stopovers': [s.to_dict() for s in self.stopovers] if self.stopovers else None,
            'schedule': self.schedule.to_dict() if self.schedule else None,
            'public': self.public,
            'operator': self.operator.to_dict() if self.operator else None,
            'price': self.price.to_dict() if self.price else None
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return leg_from_json(data)


def leg_from_json(data: dict | str | None):
    """
    Creates a Leg object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    return Leg(
        origin=place_from_json(data['origin']) if 'origin' in data else None,
        destination=place_from_json(data['destination']) if 'destination' in data else None,
        departure=_read_datetime(data['departure']) if 'departure' in data else None,
        arrival=_read_datetime(data['arrival']) if 'arrival' in data else None,
        mode=Mode.from_string(data['mode']) if 'mode' in data else None,
        sub_mode=data['subMode'] if 'subMode' in data else None,
        departure_delay=data['departureDelay'] if 'departureDelay' in data else None,
        departure_platform=data['departurePlatform'] if 'departurePlatform' in data else None,
        arrival_delay=data['arrivalDelay'] if 'arrivalDelay' in data else None,
        arrival_platform=data['arrivalPlatform'] if 'arrivalPlatform' in data else None,
        line=line_from_json(data['line']) if 'line' in data else None,
        direction=data['direction'] if 'direction' in data else None,
        stopovers=[stopover_from_json(s) for s in data['stopovers']] if 'stopovers' in data else None,
        schedule=schedule_from_json(data['schedule']) if 'schedule' in data else None,
        public=data['public'] if 'public' in data else None,
        operator=operator_from_json(data['operator']) if 'operator' in data else None,
        price=price_from_json(data['price']) if 'price' in data else None
    )


class Journey:
    """
    Represents a journey in the public transport system.
    A journey is a set of directions to get from one place to another.
    """

    def __init__(self, id: str, legs: list[Leg], price: Price = None):
        self.type = 'journey'
        self.id = id
        self.legs = legs
        self.price = price

    def to_dict(self):
        return _remove_empty_keys({
            'type': self.type,
            'id': self.id,
            'legs': [l.to_dict() for l in self.legs] if self.legs else None,
            'price': self.price.to_dict() if self.price else None
        })

    def to_json(self):
        return json.dumps(self.to_dict())

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return journey_from_json(data)


def journey_from_json(data: dict | str | None):
    """
    Creates a Journey object from a JSON object.
    :param data: The JSON dict.
    """
    if data is None:
        return None

    if isinstance(data, str):
        return Journey(data, [])

    return Journey(
        id=data['id'] if 'id' in data else None,
        legs=[leg_from_json(l) for l in data['legs']] if 'legs' in data else None,
        price=price_from_json(data['price']) if 'price' in data else None
    )


def from_json(data: dict | str | None):
    """
    Creates an FPTF object from a JSON object, depending on data type.
    :param data: The JSON dict.
    :return: The FPTF object.
    """
    if data is None:
        return None
    if isinstance(data, list):
        return [from_json(d) for d in data]
    elif isinstance(data, str):
        return data
    elif not isinstance(data, dict):
        return None

    typ = data['type']

    if typ == 'location':
        return location_from_json(data)
    elif typ == 'station':
        return station_from_json(data)
    elif typ == 'stop':
        return stop_from_json(data)
    elif typ == 'region':
        return region_from_json(data)
    elif typ == 'line':
        return line_from_json(data)
    elif typ == 'route':
        return route_from_json(data)
    elif typ == 'schedule':
        return schedule_from_json(data)
    elif typ == 'operator':
        return operator_from_json(data)
    elif typ == 'stopover':
        return stopover_from_json(data)
    elif typ == 'journey':
        return journey_from_json(data)
    elif typ == 'leg':
        return leg_from_json(data)
    elif typ == 'price':
        return price_from_json(data)
    return None
