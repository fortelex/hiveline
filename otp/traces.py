from datetime import datetime

import folium
import h3
import pandas as pd
import polyline
import skmob
import branca.colormap as cm


def get_time(timestamp):
    return datetime.utcfromtimestamp(timestamp / 1000)


def add_traces_to_map(map_f, traces, max_users=1000):
    for tdf in traces:
        map_f = tdf.plot_trajectory(map_f=map_f, max_points=None, start_end_markers=False, max_users=max_users)

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


def get_traces(db, sim_id, max_traces=None):
    route_results = db["route-results"]

    results = route_results.find({"sim-id": sim_id})

    traces = []

    for result in results:
        for option in result["options"]:
            if option is None:
                continue

            for itinerary in option["itineraries"]:
                line = []

                for leg in itinerary["legs"]:
                    points = polyline.decode(leg["legGeometry"]["points"])
                    start_date = leg["startTime"]  # unix timestamp in ms
                    if "rtStartTime" in leg:
                        start_date = leg["rtStartTime"]
                    end_date = leg["endTime"]
                    if "rtEndTime" in leg:
                        end_date = leg["rtEndTime"]

                    diff = end_date - start_date
                    num_points = len(points)

                    trajectory = [[point[0], point[1], get_time(start_date + (diff * i / num_points))] for i, point in
                                  enumerate(points)]

                    line.extend(trajectory)

                tdf = skmob.TrajDataFrame(line, latitude=0, longitude=1, datetime=2)
                traces.append(tdf)

                if max_traces is not None and len(traces) >= max_traces:
                    return traces

    return traces
