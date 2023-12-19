import json

from hiveline.od.place import Place
from hiveline.plotting.map import CityPlotter


def main():
    sim_id = "0e952d41-9b3d-4bd3-8514-fabefe1549e1"
    cache = "./cache"
    sub_type = "contribution-origin"

    place = Place("Eindhoven, Netherlands", '2020')

    heat = get_modal_heatmap(sim_id, cache, sub_type=sub_type)

    modes = ["car", "walk", "rail", "bus"]

    for mode in modes:
        mode_heat = {k: float(v[mode]) for k, v in heat.items()}

        plotter = CityPlotter(place, zoom=11)
        plotter.add_custom_hex_heatmap(mode_heat)
        plotter.export_to_png(filename=sub_type + "_" + mode + "_heatmap")


def get_modal_heatmap(sim_id: str, cache: str = "./cache", sub_type=None) -> dict:
    if sub_type is None:
        sub_type = ""
    with open(cache + "/modal-heatmaps/" + sub_type + "-" + sim_id + ".json", "r") as f:
        return json.load(f)


if __name__ == "__main__":
    main()
