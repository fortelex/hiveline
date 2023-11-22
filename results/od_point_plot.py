import os.path

import folium

from mongo.mongo import get_database

from virtual_commuter import vc_extract

# todo: move to results and use CityPlotter

sim_id = "3e173b8e-cb94-4c0d-aa07-4992f0929f95"

html_file = "./test.html"
abs_path = "file:///" + os.path.abspath(html_file)

db = get_database()

vcs = db["virtual-commuters"].find({"sim-id": sim_id})

print("Extracting points...")

vc_points = []

color_map = {
    "home": "#D280CE",
    "office": "#FE5F55",
    "commercial": "#F0B67F",
    "social": "#F7F4D3",

    # which colors should these be?
    "industrial": "#FFFF00",
    "agricultural": "#00FF00",  # never seen in paris city center (duh)
    "none": "#FFFFFF"  # school?
}

max_count = 2000
count = 0

for vc in vcs:
    if not vc_extract.should_route(vc):
        continue

    count += 1
    if count > max_count:
        break

    origin_obj = vc["origin"]
    dest_obj = vc["destination"]

    origin_point = {
        "point": [origin_obj["lat"], origin_obj["lon"]],
        "color": color_map["home"]
    }

    employment_type = vc["employment_type"]

    if employment_type is None:
        employment_type = "none"

    dest_point = {
        "point": [dest_obj["lat"], dest_obj["lon"]],
        "color": color_map[employment_type]
    }

    vc_points.append(origin_point)
    vc_points.append(dest_point)

print("Plotting points...")

def plot_points(points):
    map_f = folium.Map(location=[48.857003, 2.3492646], zoom_start=13, tiles='CartoDB dark_matter')

    for point in points:
        folium.CircleMarker(location=point["point"], radius=2, color=point["color"], fill=True, fill_color=point["color"], fill_opacity=1).add_to(map_f)

    map_f.save(html_file)

plot_points(vc_points)