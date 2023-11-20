import warnings
from datetime import datetime

import folium
import h3
import pandas as pd
import polyline
import skmob
import branca.colormap as cm


def get_time(timestamp):
    return datetime.utcfromtimestamp(timestamp / 1000)


def add_traces_to_map(map_f, traces, max_points_per_trace=None):
    warnings.filterwarnings('ignore', 'If necessary, trajectories will be down-sampled', UserWarning)
    for trace in traces:
        tdf = trace["tdf"]
        color = trace["color"]
        map_f = tdf.plot_trajectory(map_f=map_f, start_end_markers=False, max_users=1,
                                    max_points=max_points_per_trace,
                                    hex_color=color)

    return map_f


def get_a_point(traces):
    for tdf in traces:
        for _, row in tdf.iterrows():
            return row["lat"], row["lng"]


def get_trace_heatmap_data(traces):
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


# Convert H3 hexagons to geographic boundaries and create DataFrame
def __hexagon_to_polygon(hexagon):
    boundary = h3.h3_to_geo_boundary(hexagon, True)
    return [[coord[1], coord[0]] for coord in boundary]  # Switch to (lat, long)


def add_heatmap_to_map(map_f, data):
    df = pd.DataFrame([
        {"hexagon": hexagon, "count": count, "geometry": __hexagon_to_polygon(hexagon)}
        for hexagon, count in data.items()
    ])

    maximum = df['count'].max()

    # Define a color scale
    linear = cm.LinearColormap(colors=['#00ccff', '#cc6600'], index=[0, 1], vmin=0, vmax=1)
    opacity = 0.5

    # Add Hexagons to the map
    for _, row in df.iterrows():
        val = row['count'] / maximum
        color = linear(val)
        folium.Polygon(
            locations=row['geometry'],
            fill=True,
            fill_color=color,
            color=color,
            weight=1,
            fill_opacity=opacity,
            opacity=opacity,
            tooltip=f"{row['count']} trace points"
        ).add_to(map_f)

    # Add color scale legend
    linear.add_to(map_f)

    return map_f


def get_simulation_traces(db, sim_id, max_traces=None):
    route_results = db["route-results"]

    results = route_results.find({"sim-id": sim_id})

    return extract_traces(results, max_traces)


def extract_traces(route_results, max_traces=None, selection=None):
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
