import datetime
from abc import ABC, abstractmethod

from hiveline.routing import fptf


class RoutingClient(ABC):
    @abstractmethod
    def get_journey(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, departure: datetime.datetime,
                    modes: list[fptf.Mode]) -> fptf.Journey | None:
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
