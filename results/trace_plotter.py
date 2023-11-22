from visualization.plot import traces
from mongo.mongo import get_database

from decision import congestion, modal_shares
from od.place import Place
from visualization.plot.map import CityPlotter


def plot_animation(sim_id, place_name, only_use_selected=False, zoom_level=13, tall_city=False, fps=30, duration=30,
                   max_points_per_trace=100):
    db = get_database()

    results = list(congestion.find_all_journeys(db, sim_id))

    selection = [None] * len(results)

    if only_use_selected:
        result_options = congestion.find_matching_route_options(db, sim_id, results)

        modal_shares.get_modal_share(result_options, out_selection=selection)

    print("Extracting traces...")
    all_to_plot = traces.extract_traces(results, selection=selection)

    print("Decimating traces...")
    # tdf = compression.compress(tdf, spatial_radius_km=spatial_radius)

    # heatmap_data = traces.get_trace_heatmap_data(to_plot)
    # map_f = traces.add_heatmap_to_map(map_f, heatmap_data)

    print("Plotting traces...")

    total_frames = fps * duration

    num_to_plot = 1
    num_step = int(len(all_to_plot) / total_frames)

    place = Place(place_name)

    plotter = CityPlotter(place, zoom=zoom_level)
    webdriver = plotter.setup_webdriver()

    for i in range(total_frames):
        print(f"Frame {i} of {total_frames}")

        to_plot = all_to_plot[:num_to_plot]

        plotter.get_map(zoom=zoom_level, dark=True)

        plotter.map = traces.add_traces_to_map(plotter.map, to_plot,
                                               max_points_per_trace=max_points_per_trace)

        plotter.export_to_png(folder="animation", filename=sim_id + "-frame-" + str(i) + ".png", tall_city=tall_city,
                              webdriver=webdriver)

        num_to_plot += num_step


def plot_all(sim_id):
    db = get_database()

    route_results = db["route-results"]

    place = Place("Paris, France")

    results = route_results.find({"sim-id": sim_id})

    print("Extracting traces...")
    all_to_plot = traces.extract_traces(results)

    plotter = CityPlotter(place, zoom=13)

    plotter.map = traces.add_traces_to_map(plotter.map, all_to_plot)

    plotter.export_to_png(filename="test.png")


if __name__ == "__main__":
    plot_animation("ae945a7c-5fa7-4312-b9c1-807cb30b3008", "Dublin Region, Ireland", zoom_level=11,
                   only_use_selected=True,
                   fps=30, duration=10, tall_city=True)
    #  plot_all("ae945a7c-5fa7-4312-b9c1-807cb30b3008")
