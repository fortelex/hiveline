from datetime import datetime

import h3
import polyline
import skmob


def get_time(timestamp):
    return datetime.utcfromtimestamp(timestamp / 1000)


def get_a_point(traces):
    for tdf in traces:
        for _, row in tdf.iterrows():
            return row["lat"], row["lng"]


def get_trace_heatmap_data(traces):
    """
    Converts trace data to a dictionary with the h3 hexagon id as key and the heat value as value. You can use this
    in a CityPlotter instance to add a custom heatmap.
    :param traces: list of trace objects. each trace object is a dict with keys: tdf, color where tdf is a
    TrajDataFrame and color is a hex color string
    :return: a dictionary with the h3 hexagon id as key and the heat value as value
    """
    data = {}

    for tdf in traces:
        for _, row in tdf.iterrows():
            lon = row["lng"]
            lat = row["lat"]

            tile = h3.geo_to_h3(lat, lon, 8)

            if tile not in data:
                data[tile] = 0

            data[tile] += 1

    return data


def extract_traces(route_results, max_traces=None, selection=None):
    """
    Extracts traces from route results
    :param route_results: the route results
    :param max_traces: the maximum number of traces to extract
    :param selection: the selected option for each route result (from decision module)
    :return: a list of trace objects. each object contains a tdf (skmob.TrajDataFrame) and a color
    """
    traces = []

    color_map = {
        "walk": "#D280CE",
        "car": "#FE5F55",
        "bus": "#F0B67F",
        "rail": "#F7F4D3"
    }

    for i, result in enumerate(route_results):
        selected_option = None
        if selection is not None:
            selected_option = selection[i]

        for option in result["options"]:
            if option is None:
                continue

            option_id = option["route-option-id"]

            if selected_option is not None and option_id != selected_option:
                continue

            for itinerary in option["itineraries"]:
                line = []

                rail_usage = 0
                bus_usage = 0
                walk_usage = 0
                car_usage = 0

                for leg in itinerary["legs"]:
                    points = polyline.decode(leg["legGeometry"]["points"])
                    start_date = leg["startTime"]  # unix timestamp in ms
                    if "rtStartTime" in leg:
                        start_date = leg["rtStartTime"]
                    end_date = leg["endTime"]
                    if "rtEndTime" in leg:
                        end_date = leg["rtEndTime"]

                    duration = end_date - start_date
                    num_points = len(points)

                    trajectory = [[point[0], point[1], get_time(start_date + (duration * i / num_points)), option_id]
                                  for i, point in
                                  enumerate(points)]

                    line.extend(trajectory)

                    mode = leg["mode"].lower()

                    if mode == "walk":
                        walk_usage += duration
                    elif mode == "car":
                        car_usage += duration
                    elif mode == "bus":
                        bus_usage += duration
                    elif mode == "rail" or mode == "subway" or mode == "tram":
                        rail_usage += duration

                longest_mode = "rail"
                longest_duration = rail_usage

                if car_usage > longest_duration:
                    longest_mode = "car"
                    longest_duration = car_usage

                if bus_usage > longest_duration:
                    longest_mode = "bus"
                    longest_duration = bus_usage

                if rail_usage > longest_duration:
                    longest_mode = "rail"
                    longest_duration = rail_usage

                if car_usage == 0 and bus_usage == 0 and rail_usage == 0:
                    longest_mode = "walk"
                    longest_duration = walk_usage

                tdf = skmob.TrajDataFrame(line, latitude=0, longitude=1, datetime=2, user_id=3)
                traces.append({
                    "tdf": tdf,
                    "color": color_map[longest_mode]
                })

                if max_traces is not None and len(traces) >= max_traces:
                    return traces

    return traces
