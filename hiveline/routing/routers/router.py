from abc import ABC, abstractmethod


class Router(ABC):
    @abstractmethod
    def get_journey(self, from_lat, from_lon, to_lat, to_lon, departure, modes):
        """
        Get a route from the router
        :param from_lat: the latitude of the starting point
        :param from_lon: the longitude of the starting point
        :param to_lat: the latitude of the destination
        :param to_lon: the longitude of the destination
        :param departure: the departure time as datetime object
        :param modes: the fptf modes to use for routing
        :return: a single fptf journey
        """
        pass
