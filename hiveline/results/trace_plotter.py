from hiveline.od.place import Place
from hiveline.plotting.map import CityPlotter, get_line_traces_by_mode, add_line_traces
from hiveline.results.journeys import Journeys
from hiveline.results.modal_shares import decide, Params


def _prepare_traces(journeys: Journeys, only_use_selected=True):
    selection: list[str] | None = None

    if only_use_selected:
        selection = journeys.get_selection(lambda options: decide(options, Params()))

    print("Extracting traces...")

    return [trace for trace in journeys.iterate_traces(selection)]


def plot_trace_animation(journeys: Journeys, only_use_selected=True, zoom_level=13, tall_city=False, fps=30,
                         duration=30):
    raw_traces = _prepare_traces(journeys, only_use_selected=only_use_selected)

    print("Plotting traces...")

    total_frames = fps * duration

    num_to_plot = 0
    num_step = int(len(raw_traces) / total_frames)

    plotter = CityPlotter(place, zoom=zoom_level)
    webdriver = plotter.setup_webdriver()

    traces = {}

    for i in range(total_frames):
        print(f"Frame {i} of {total_frames}")

        raw_to_add = raw_traces[num_to_plot:num_to_plot + num_step]
        traces_to_add = get_line_traces_by_mode(raw_to_add)
        traces = add_line_traces(traces, traces_to_add)

        plotter.get_map(zoom=zoom_level, dark=True)
        plotter.add_traces(traces)

        plotter.export_to_png(folder="animation", filename=sim_id + "-frame-" + str(i), tall_city=tall_city,
                              webdriver=webdriver)

        num_to_plot += num_step


def plot_traces(journeys: Journeys, place, only_use_selected=True, folder="images/", filename="image"):
    raw_traces = _prepare_traces(journeys, only_use_selected=only_use_selected)
    traces = get_line_traces_by_mode(raw_traces)

    print("Plotting traces...")

    plotter = CityPlotter(place, zoom=11)

    plotter.add_city_shape(color="yellow", weight=10)
    plotter.add_traces(traces)

    return plotter.export_to_png(folder=folder, filename=filename)


if __name__ == "__main__":
    sim_place = Place("Eindhoven, Netherlands", '2020')
    jrn = Journeys("614aab43-b799-46cd-a1aa-bdb9e739d525")
    plot_traces(jrn, sim_place)
    # plot_trace_animation("614aab43-b799-46cd-a1aa-bdb9e739d525", place, zoom_level=11,
    #                only_use_selected=True,
    #                fps=30, duration=2, tall_city=True)
