import json

from hiveline.od.place import Place
from hiveline.plotting.map import CityPlotter


def main():
    sim_id = "bd6809da-8113-469f-91cc-501549e8df68"
    cache = "./cache"

    place = Place("Eindhoven, Netherlands")

    heat = get_modal_heatmap(sim_id, cache)

    modes = ["car", "walk", "rail", "bus"]

    for mode in modes:
        mode_heat = {k: float(v[mode]) for k, v in heat.items()}

        plotter = CityPlotter(place, zoom=11)
        plotter.add_custom_hex_heatmap(mode_heat)
        plotter.export_to_png(filename=mode + "_heatmap")


def get_modal_heatmap(sim_id: str, cache: str = "./cache") -> dict:
    with open(cache + "/modal-heatmaps/" + sim_id + ".json", "r") as f:
        return json.load(f)


if __name__ == "__main__":
    main()
