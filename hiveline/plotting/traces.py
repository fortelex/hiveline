from datetime import datetime

import h3

from hiveline.models import fptf


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


def _get_loc(place):
    typ = place["type"]
    if typ == "location":
        return place["latitude"], place["longitude"]

    if typ == "station":
        if not place["location"]:
            return None

        return place["location"]["latitude"], place["location"]["longitude"]

    if typ == "stop":
        if place["location"]:
            return place["location"]["latitude"], place["location"]["longitude"]

        if place["station"] and place["station"]["location"]:
            return place["station"]["location"]["latitude"], place["station"]["location"]["longitude"]

        return None

    return None


def __extract_stopover(stopover):
    loc = _get_loc(stopover["stop"])

    t = fptf.read_datetime(stopover["departure"]) if "departure" in stopover else None
    if t is None:
        t = fptf.read_datetime(stopover["arrival"])

    return [loc[0], loc[1], t]


def __extract_trace(result, color_map, selection=None, i=0, max_points_per_trace=100):
    selected_option_id = None
    if selection is not None:
        selected_option_id = selection[i]

    traces = []

    for option in result["options"]:
        if option is None:
            continue

        option_id = option["route-option-id"]

        if selected_option_id is not None and option_id != selected_option_id:
            continue

        if ("journey" not in option) or (not option["journey"]) or ("legs" not in option["journey"]) or (
                not option["journey"]["legs"]):
            continue

        rail_usage = 0
        bus_usage = 0
        walk_usage = 0
        car_usage = 0

        line = []

        for leg in option["journey"]["legs"]:
            departure = fptf.read_datetime(leg["departure"])
            arrival = fptf.read_datetime(leg["arrival"])

            duration = (arrival - departure).total_seconds()

            mode = leg["mode"]

            if mode == "walking":
                walk_usage += duration
            elif mode == "car":
                car_usage += duration
            elif mode == "bus":
                bus_usage += duration
            elif mode == "train":
                rail_usage += duration

            if not leg["stopovers"]:
                origin_loc = _get_loc(leg["origin"])
                dest_loc = _get_loc(leg["destination"])

                if origin_loc and dest_loc:
                    line.append([origin_loc[0], origin_loc[1], leg["departure"]])
                    line.append([dest_loc[0], dest_loc[1], leg["arrival"]])
                else:
                    print("No origin or destination location found for leg")

                continue

            leg_trace = [__extract_stopover(stopover) for stopover in leg["stopovers"]]
            line.extend(leg_trace)

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

        if len(line) > max_points_per_trace:
            di = max(1, int(len(line) / max_points_per_trace))
            line = line[::di]

        traces.append({
            "trace": line,
            "color": color_map[longest_mode]
        })

    return traces


def extract_traces(route_results: list[dict], selection=None, max_points_per_trace=100):
    """
    Extracts trace_lists from route results
    :param route_results: the route results
    :param selection: the selected option for each route result (from decision module)
    :param max_points_per_trace: max number of points to plot per trace
    :return: a list of trace objects. each object contains a tdf (skmob.TrajDataFrame) and a color
    """
    color_map = {
        "walk": "#D280CE",
        "car": "#FE5F55",
        "bus": "#F0B67F",
        "rail": "#F7F4D3"
    }

    trace_lists = [__extract_trace(result, color_map, selection, j, max_points_per_trace) for (j, result) in
                   enumerate(route_results)]

    return [trace for trace_list in trace_lists for trace in trace_list]
