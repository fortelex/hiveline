import time
from datetime import datetime, date


def extract_origin_loc(vc):
    """
    Extract the origin location from a virtual commuter
    :param vc: the virtual commuter
    :return: the origin location as array [lon, lat]
    """
    origin = vc["origin"]

    return [origin["lon"], origin["lat"]]


def extract_destination_loc(vc):
    """
    Extract the destination location from a virtual commuter
    :param vc: the virtual commuter
    :return: the destination location as array [lon, lat]
    """
    destination = vc["destination"]

    return [destination["lon"], destination["lat"]]


def extract_departure(vc, sim) -> datetime:
    """
    Extract the departure time from a virtual commuter or simulation
    :param vc: the virtual commuter
    :param sim: the simulation
    :return: the departure time
    """
    return datetime.strptime(sim["sim-date"] + "T08:00:00Z", "%Y-%m-%dT%H:%M:%SZ")


def has_motor_vehicle(vc):
    """
    Check if the route finder should add car routes
    :param vc: the virtual commuter
    :return: True if the virtual commuter has a motor vehicle, False otherwise
    """

    if "vehicles" not in vc:
        return False

    vehicles = vc["vehicles"]
    motor_keys = ["car", "moto", "van", "utilities"]

    for key in motor_keys:
        if key not in vehicles:
            continue

        vehicle = vehicles[key]
        if vehicle is None:
            continue

        if type(vehicle) != int:
            continue

        if vehicle > 0:
            return True

    return False


def has_motorcycle(vc):
    """
    Check if the virtual commuter has a motorcycle (Used for congestion buff)
    :param vc: the virtual commuter
    :return: True if the virtual commuter has a motorcycle, False otherwise
    """
    if "vehicles" not in vc:
        return False

    vehicles = vc["vehicles"]

    if "moto" not in vehicles:
        return False

    moto_value = vehicles["moto"]

    if moto_value is None or int(moto_value) == 0:
        return False

    return True


def extract_traveller(vc):
    """
    Extracts traveller information from a virtual commuter, like employment or vehicles.
    This should contain all metadata that will be used in the decision function
    :param vc: the virtual commuter
    :return:
    """

    created = vc["created"]

    # check if created is a string
    if type(created) == str:
        # convert to datetime
        created = datetime.strptime(created, "%d-%m-%Y %H:%M:%S")

    return {
        "employed": vc["employed"],
        "employment_type": vc["employment_type"],
        "vehicles": vc["vehicles"],
        "age": vc["age"],
        "vc-created": created,
    }


def would_use_motorized_vehicle(vc):
    """
    Check if the virtual commuter would use a motorized vehicle based on the usage field in vehicles
    :param vc: the virtual commuter
    :return: True if the virtual commuter would use a motorized vehicle, False otherwise
    """
    if "vehicles" not in vc:
        return False

    vehicles = vc["vehicles"]

    if "usage" not in vehicles:
        return False

    usage = vehicles["usage"]

    if usage is None:
        return False

    if type(usage) != str:
        return False

    if usage is None:
        return False

    return True


def __validate_location(loc):
    """
    Validate a location
    :param loc: the location
    :return: True if the location is valid, False otherwise
    """
    if "lat" not in loc:
        return False
    if "lon" not in loc:
        return False
    if loc["lat"] is None or type(loc["lat"]) != float:
        return False
    if loc["lon"] is None or type(loc["lon"]) != float:
        return False

    return True


def should_route(vc):
    """
    Check if the virtual commuter should be routed
    :param vc: the virtual commuter
    :return: True if the virtual commuter should be routed, False otherwise
    """
    if "origin" not in vc:
        return False
    if "destination" not in vc:
        return False
    if not __validate_location(vc["origin"]):
        return False
    if not __validate_location(vc["destination"]):
        return False

    return True
