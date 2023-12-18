import datetime

import polyline
import requests

from hiveline.routing.clients.routing_client import RoutingClient
from hiveline.models import fptf


class OpenTripPlannerRoutingClient(RoutingClient):
    def __init__(self, client_timeout=40):
        """
        :param client_timeout: timeout for the request
        """
        self.client_timeout = client_timeout

    def get_journeys(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, departure: datetime.datetime,
                     modes: list[fptf.Mode]) -> list[fptf.Journey] | None:
        """
        This function queries the OTP GraphQL endpoint and returns the itineraries

        :param from_lat: latitude of the starting point
        :param from_lon: longitude of the starting point
        :param to_lat: latitude of the destination
        :param to_lon: longitude of the destination
        :param departure: departure time as datetime object
        :param modes: list of fptf modes to use for routing

        :return: a single fptf journey
        """

        if modes is None:
            modes = [fptf.Mode.WALKING, fptf.Mode.TRAIN, fptf.Mode.BUS]

        # get otp modes from fptf modes
        otp_modes = []
        for mode in modes:
            if mode == fptf.Mode.WALKING:
                otp_modes.append("WALK")
            elif mode == fptf.Mode.BUS:
                otp_modes.append("BUS")
                otp_modes.append("TROLLEYBUS")
            elif mode == fptf.Mode.TRAIN:
                otp_modes.append("RAIL")
                otp_modes.append("TRAM")
                otp_modes.append("SUBWAY")
                otp_modes.append("CABLE_CAR")
                otp_modes.append("FUNICULAR")
                otp_modes.append("MONORAIL")
            elif mode == fptf.Mode.GONDOLA:
                otp_modes.append("GONDOLA")
            elif mode == fptf.Mode.AIRCRAFT:
                otp_modes.append("AIRPLANE")
            elif mode == fptf.Mode.WATERCRAFT:
                otp_modes.append("FERRY")
            elif mode == fptf.Mode.TAXI:
                otp_modes.append("TAXI")
            elif mode == fptf.Mode.BICYCLE:
                otp_modes.append("BIKE")
            elif mode == fptf.Mode.CAR:
                otp_modes.append("CAR")

        # build query
        url = "http://localhost:8080/otp/routers/default/index/graphql"

        date = departure.strftime("%Y-%m-%d")
        time = departure.strftime("%H:%M")

        mode_str = '{mode: ' + '} {mode:'.join(otp_modes) + '}'

        query = """
        {
            plan(
                from: { lat:%s,lon:%s}
                to: {lat:%s,lon:%s}
                date: "%s"
                time: "%s"
              
                transportModes: [%s]) {
                itineraries {
                    startTime
                    endTime
                    legs {
                        mode
                        startTime
                        endTime
                        agency {
                            id
                            name
                            gtfsId
                        }
                        from {
                            stop {
                                gtfsId
                            }
                            name
                            lat
                            lon
                            departureTime
                            arrivalTime
                        }
                        to {
                            stop {
                                gtfsId
                            }
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
                        }
                        intermediatePlaces {
                            stop {
                                gtfsId
                            }
                            name
                            lon
                            lat
                            departureTime
                            arrivalTime
                        }
                        legGeometry {
                            points
                        }
                    }
                }
            }
        }
        """ % (from_lat, from_lon, to_lat, to_lon, date, time, mode_str)

        headers = {
            'Content-Type': 'application/json'
        }

        # Send the request to the OTP GraphQL endpoint
        response = requests.post(url, json={'query': query}, headers=headers, timeout=self.client_timeout)

        # Check if the request was successful
        if response.status_code != 200:
            print("Error querying OpenTripPlanner:", response.status_code)
            print(response.json())

            return None

        json_data = response.json()

        if not json_data or "data" not in json_data or "errors" in json_data:
            print("OTP may have failed to parse the request. Query:")
            print(query)
            print("Response:")
            print(json_data)

            return None

        otp_resp = OtpResponse(json_data)

        journeys = otp_resp.transform()
        if len(journeys) == 0:
            return []

        return journeys


class OtpResponse:
    def __init__(self, data):
        self.itineraries = [OtpItinerary(itinerary) for itinerary in data['data']['plan']['itineraries']]

    def transform(self):
        return [itinerary.transform() for itinerary in self.itineraries]


class OtpItinerary:
    def __init__(self, itinerary):
        self.start_time = itinerary['startTime']
        self.end_time = itinerary['endTime']
        self.legs = [OtpLeg(leg) for leg in itinerary['legs']]

    def transform(self):
        return fptf.Journey(
            id=None,
            legs=[leg.transform() for leg in self.legs],
        )


class OtpLeg:
    def __init__(self, leg):
        self.mode = leg['mode']
        self.start_time = leg['startTime']
        self.end_time = leg['endTime']
        self.agency = OtpAgency(leg['agency']) if 'agency' in leg and leg['agency'] else None
        self.from_place = OtpPlace(leg['from'])
        self.to = OtpPlace(leg['to'])
        self.route = OtpRoute(leg['route']) if 'route' in leg and leg['route'] else None
        self.intermediate_places = [OtpPlace(place) for place in
                                    leg['intermediatePlaces']] if 'intermediatePlaces' in leg and leg[
            'intermediatePlaces'] else []
        self.geometry = leg['legGeometry']['points'] if 'legGeometry' in leg and 'points' in leg['legGeometry'] else ''

    def transform(self):
        mode = transform_mode(self.mode)
        return fptf.Leg(
            origin=self.from_place.transform_to_stop_station(),
            destination=self.to.transform_to_stop_station(),
            departure=self.from_place.transform_to_departure(),
            arrival=self.to.transform_to_arrival(),
            mode=mode,
            sub_mode=self.mode.lower(),
            operator=self.agency.transform() if self.agency else None,
            line=self.route.transform(mode) if self.route else None,
            stopovers=self.transform_stopovers()
        )

    def transform_stopovers(self):
        if self.intermediate_places:
            return [place.transform_to_stopover() for place in [self.from_place] + self.intermediate_places + [self.to]]
        elif self.geometry:
            return self._stopovers_from_geom()
        return [self.from_place.transform_to_stopover(), self.to.transform_to_stopover()]

    def _stopovers_from_geom(self):
        geom = polyline.decode(self.geometry)
        dep = self.start_time
        arr = self.end_time
        step = (arr - dep) / len(geom)
        stopovers = [self.from_place.transform_to_stopover()]

        for i, point in enumerate(geom):
            t = dep + i * step
            dt = datetime.datetime.fromtimestamp(t / 1000)

            stopovers.append(fptf.Stopover(
                stop=fptf.Station(
                    id='',
                    name='',
                    location=fptf.Location(
                        latitude=point[0],
                        longitude=point[1]
                    )
                ),
                arrival=dt,
                departure=dt
            ))

        stopovers.append(self.to.transform_to_stopover())

        return stopovers


def transform_mode(mode):
    modes = {
        'WALK': fptf.Mode.WALKING,
        'BUS': fptf.Mode.BUS,
        'RAIL': fptf.Mode.TRAIN,
        'TRAM': fptf.Mode.TRAIN,
        'SUBWAY': fptf.Mode.TRAIN,
        'TRANSIT': fptf.Mode.TRAIN,
        'BICYCLE': fptf.Mode.BICYCLE,
        'CAR': fptf.Mode.CAR
    }
    return modes.get(mode, '')


class OtpAgency:
    def __init__(self, agency):
        self.id = agency['id']
        self.name = agency['name']
        self.gtfs_id = agency['gtfsId']

    def transform(self):
        return fptf.Operator(
            id=self.id,
            name=self.name
        )


class OtpPlace:
    def __init__(self, place):
        self.stop = OtpStop(place['stop']) if 'stop' in place and place['stop'] else None
        self.name = place['name']
        self.lat = place['lat']
        self.lon = place['lon']
        self.departure_time = place['departureTime']
        self.arrival_time = place['arrivalTime']

    def transform_to_stop_station(self):
        id = self.stop.gtfs_id if self.stop else ''
        return fptf.Station(
            id=id,
            name=self.name,
            location=fptf.Location(
                latitude=self.lat,
                longitude=self.lon
            )
        )

    def transform_to_departure(self):
        return datetime.datetime.fromtimestamp(self.departure_time / 1000)

    def transform_to_arrival(self):
        return datetime.datetime.fromtimestamp(self.arrival_time / 1000)

    def transform_to_stopover(self):
        return fptf.Stopover(
            stop=self.transform_to_stop_station(),
            arrival=self.transform_to_arrival(),
            departure=self.transform_to_departure()
        )


class OtpStop:
    def __init__(self, stop):
        self.gtfs_id = stop['gtfsId']


class OtpRoute:
    def __init__(self, route):
        self.gtfs_id = route['gtfsId']
        self.long_name = route['longName']
        self.short_name = route['shortName']

    def transform(self, mode: fptf.Mode):
        return fptf.Line(
            id=self.gtfs_id,
            name=self.long_name,
            mode=mode,
            routes=None,
            operator=None
        )


if __name__ == "__main__":
    OpenTripPlannerRoutingClient().get_journeys(52.520008, 13.404954, 52.516667, 13.383333, datetime.datetime.now(),
                                                ["WALK", "TRANSIT"])
