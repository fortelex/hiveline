import folium

import traces
from mongo.mongo import get_database

sim_id = "e0713278-78a1-4b95-88bb-d54df24f7d5e"

db = get_database()

route_results = db["route-results"]

results = route_results.find({"sim-id": sim_id})

to_plot = traces.extract_traces(results)
#to_plot = traces.get_simulation_traces(db, sim_id)

print(to_plot)

some_point = traces.get_a_point(to_plot)

# Create Folium Map
map_f = folium.Map(location=some_point, zoom_start=11)  # Adjust the location and zoom level

map_f = traces.add_traces_to_map(map_f, to_plot, max_users=1000)
# heatmap_data = traces.get_trace_heatmap_data(to_plot)
# map_f = traces.add_heatmap_to_map(map_f, heatmap_data)

map_f.save("test.html")
