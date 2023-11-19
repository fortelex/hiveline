import os.path
import time

import folium

import traces
from mongo.mongo import get_database
from selenium import webdriver

sim_id = "0ee97ddf-333e-4f62-b3de-8d7f52459065"

html_file = "./test.html"
abs_path = "file:///" + os.path.abspath(html_file)

db = get_database()

route_results = db["route-results"]

results = route_results.find({"sim-id": sim_id})

print("Extracting traces...")
all_to_plot = traces.extract_traces(results)

# heatmap_data = traces.get_trace_heatmap_data(to_plot)
# map_f = traces.add_heatmap_to_map(map_f, heatmap_data)

print("Plotting traces...")

options = webdriver.ChromeOptions()
options.add_argument("--headless")

driver = webdriver.Chrome(options=options)
driver.set_window_size(1920, 1080)

fps = 30
total_duration = 30  # seconds
total_frames = fps * total_duration

num_to_plot = 1
num_step = int(len(all_to_plot) / total_frames)

for i in range(total_frames):
    print(f"Frame {i} of {total_frames}")

    to_plot = all_to_plot[:num_to_plot]

    map_f = folium.Map(location=[48.857003, 2.3492646], zoom_start=13, tiles='CartoDB dark_matter')

    map_f = traces.add_traces_to_map(map_f, to_plot, max_users=1000)

    map_f.save(html_file)

    driver.get(abs_path)
    time.sleep(0.2)
    driver.save_screenshot("otp/output/" + sim_id + "-frame-" + str(i) + ".png")

    num_to_plot += num_step


