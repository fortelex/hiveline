import datetime
import json

import requests
from .routing_client import RoutingClient
from .. import fptf


class BifrostRoutingClient(RoutingClient):
    def __init__(self, client_timeout=40):
        """
        :param client_timeout: timeout for the request
        """
        self.client_timeout = client_timeout

    def get_journeys(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, departure: datetime.datetime,
                     modes: list[fptf.Mode]) -> list[fptf.Journey] | None:
        """
        This function queries the Bifrost API and returns the itineraries

        :param from_lat: latitude of the starting point
        :param from_lon: longitude of the starting point
        :param to_lat: latitude of the destination
        :param to_lon: longitude of the destination
        :param departure: departure time as datetime object
        :param modes: the fptf modes to use for routing

        :return: list of fptf journeys
        """
        url = "http://localhost:8090/bifrost"

        origin = {
            "type": "location",
            "latitude": from_lat,
            "longitude": from_lon
        }

        destination = {
            "type": "location",
            "latitude": to_lat,
            "longitude": to_lon
        }

        # set time zone to CET
        departure = departure.astimezone(datetime.timezone(datetime.timedelta(hours=1)))

        req = {
            "origin": origin,
            "destination": destination,
            "modes": [mode.to_string() for mode in modes],
            "departure": departure.isoformat()
        }

        headers = {
            'Content-Type': 'application/json'
        }

        # Send the request to the OTP GraphQL endpoint
        response = requests.post(url, json=req, headers=headers, timeout=self.client_timeout)

        if response.status_code != 200:
            print("Error querying Bifrost:", response.status_code)
            print(response.text)
            return None

        result = response.json()

        return [fptf.journey_from_json(result)]
