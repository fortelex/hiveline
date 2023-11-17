import folium

import traces
from mongo.mongo import get_database

db = get_database()

to_plot = traces.get_traces(db, "df2aa812-d0c2-4fb8-aa4c-d0ed6fd0c900")

some_point = traces.get_a_point(to_plot)

# Create Folium Map
map_f = folium.Map(location=some_point, zoom_start=11)  # Adjust the location and zoom level

# map_f = traces.add_traces_to_map(map_f, to_plot, max_users=1000)
heatmap_data = traces.get_trace_heatmap_data(to_plot)
map_f = traces.add_heatmap_to_map(map_f, heatmap_data)

map_f.save("test.html")
