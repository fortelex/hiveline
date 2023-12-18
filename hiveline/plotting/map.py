import datetime
import os
import sys
import time

import folium
import h3
import matplotlib.cm as cm
import matplotlib.colors
import matplotlib.colors as mpl_colors
import pandas as pd
from dotenv import load_dotenv
from geojson import LineString
from selenium import webdriver

from hiveline.models import fptf

load_dotenv()
PROJECT_PATH = os.getenv("PROJECT_PATH")
if not PROJECT_PATH.endswith("/"):
    PROJECT_PATH += "/"
sys.path.append(PROJECT_PATH)


def get_mpl_color(value, colormap_name='magma'):
    colormap = cm.get_cmap(colormap_name)
    color = colormap(value)
    color = mpl_colors.rgb2hex(color)
    return color


def style_heatmap(feature):
    return {
        'fillColor': feature['geometry']['color'],
        'color': 'black',  # # Set the border color
        'weight': 1,  # Set the border width
        'fillOpacity': 0.6,  # Set the fill opacity 
    }


# Convert H3 hexagons to geographic boundaries and create DataFrame
def _hexagon_to_polygon(hexagon):
    boundary = h3.h3_to_geo_boundary(hexagon, True)
    return [[coord[1], coord[0]] for coord in boundary]  # Switch to (lat, long)


def _extract_mode_traces(trace: list[tuple[tuple[float, float], datetime.datetime, fptf.Mode, bool]]) -> list[
    tuple[LineString, fptf.Mode]]:
    last_mode = trace[0][2]
    line = []
    traces = []

    for point, _, mode, _ in trace:
        if mode != last_mode:
            traces.append((LineString(line), last_mode))
            line = []
        line.append(point)
        last_mode = mode

    if line:
        traces.append((LineString(line), last_mode))
    return traces


def get_line_traces_by_mode(traces: list[list[tuple[tuple[float, float], datetime.datetime, fptf.Mode, bool]]]) -> dict[
    fptf.Mode, list[LineString]]:
    mode_trace_lists = [_extract_mode_traces(trace) for trace in traces]
    mode_traces = [item for sublist in mode_trace_lists for item in sublist]

    # group traces by mode
    traces_by_mode = {}

    for line, mode in mode_traces:
        if mode not in traces_by_mode:
            traces_by_mode[mode] = []
        traces_by_mode[mode].append(line)

    return traces_by_mode


def add_line_traces(a: dict[fptf.Mode, list[LineString]], b: dict[fptf.Mode, list[LineString]]) -> dict[
    fptf.Mode, list[LineString]]:
    for mode, traces in b.items():
        if mode not in a:
            a[mode] = []
        a[mode].extend(traces)

    return a


class CityPlotter():
    def __init__(self, city, zoom=13):
        self.city = city
        # if len(city.data.columns) <= 3:
        #     self.city.load_all()
        self.centroid = self.get_centroid()  # [48.857003, 2.3492646]
        self.map = self.get_map(zoom)

    def get_centroid(self):
        proj_shape = self.city.shape.to_crs('EPSG:3857')
        centroid = proj_shape.centroid
        c = centroid.to_crs(self.city.shape.crs)
        return [c.y, c.x]

    def get_map(self, zoom, dark=True):
        mapstyle = 'cartodbdark_matter' if dark else 'CartoDB positron'
        m = folium.Map(location=self.centroid, zoom_start=zoom, tiles=mapstyle, zoom_control=False)
        return m

    def add_city_shape(self, color="white", opacity=0.6, weight=3, dash_array='0, 0'):
        shape = self.city.shape.boundary.__geo_interface__
        shape = folium.GeoJson(data=shape,
                               style_function=lambda feature: dict(color=color, weight=weight, opacity=opacity,
                                                                   dashArray=dash_array))
        shape.add_to(self.map)

    def add_hex_heatmap(self, column):
        max_val = self.city.data[column].max()

        # add each tile to the map with the corresponding color
        for _, tile in self.city.data.iterrows():
            geo_j = tile["geometry"].__geo_interface__
            geo_j['color'] = get_mpl_color(tile[column] / max_val)
            geo_j = folium.GeoJson(data=geo_j, style_function=style_heatmap)
            geo_j.add_to(self.map)

    def add_custom_hex_heatmap(self, data):
        """
        Add a custom heatmap to the map. For adding city input data, use add_hex_heatmap instead.
        :param data: a dictionary with the h3 hexagon id as key and the heat value as value
        :return:
        """
        df = pd.DataFrame([
            {"hexagon": hexagon, "count": count, "geometry": _hexagon_to_polygon(hexagon)}
            for hexagon, count in data.items()
        ])

        maximum = df['count'].max()
        minimum = df['count'].min()

        # Define a color scale
        # linear = cm.LinearColormap(colors=['#00ccff', '#cc6600'], index=[0, 1], vmin=0, vmax=1)
        linear = cm.get_cmap("viridis")
        opacity = 1

        # Add Hexagons to the map
        for _, row in df.iterrows():
            val = (row['count'] - minimum) / (maximum - minimum)
            color = matplotlib.colors.rgb2hex(linear(val))
            folium.Polygon(
                locations=row['geometry'],
                fill=True,
                fill_color=color,
                color=color,
                weight=1,
                fill_opacity=opacity,
                opacity=opacity,
                tooltip=f"{row['count']} trace points"
            ).add_to(self.map)

    def show_map(self):
        return display(self.map)

    def setup_webdriver(self):
        """
        Creates a new headless chrome webdriver instance
        :return: webdriver instance
        """
        options = webdriver.ChromeOptions()
        # do not show chrome
        options.add_argument("--headless")
        driver = webdriver.Chrome(options=options)
        return driver

    def style_function(self, color, weight=2, opacity=0.75, dash_array='0, 0'):
        return dict(color=color, weight=weight, opacity=opacity, dashArray=dash_array)

    def get_style_function(self, color, weight=2, opacity=0.75, dash_array='0, 0'):
        return lambda feature: self.style_function(color, weight, opacity, dash_array)

    def add_traces(self, traces: dict[fptf.Mode, list[LineString]], weight=2,
                   opacity=0.75, dash_array='0, 0'):
        """
        Add traces to the map
        :param traces: list of trace objects. each trace object is a dict with keys: tdf, color where tdf is a
        trajectory and color is a hex color string
        :param weight: weight of the trace line
        :param opacity: opacity of the trace line
        :param dash_array: dash array of the trace line
        :return:
        """
        color_map = {
            fptf.Mode.WALKING: "#D280CE",
            fptf.Mode.CAR: "#FE5F55",
            fptf.Mode.BUS: "#F0B67F",
            fptf.Mode.TRAIN: "#F7F4D3",
            fptf.Mode.GONDOLA: "#F7F4D3",
            fptf.Mode.WATERCRAFT: "#F7F4D3"
        }

        draw_order = [fptf.Mode.WALKING, fptf.Mode.CAR, fptf.Mode.BUS, fptf.Mode.TRAIN, fptf.Mode.GONDOLA,
                      fptf.Mode.WATERCRAFT]

        for mode in draw_order:
            color = color_map[mode]

            for line in traces.get(mode, []):
                tgeojson = folium.GeoJson(line,
                                          name='tgeojson',
                                          style_function=self.get_style_function(color, weight, opacity, dash_array)
                                          )
                tgeojson.add_to(self.map)

    def export_to_png(self, folder='images/', filename='image', tall_city=False, webdriver=None):
        if webdriver is None:
            webdriver = self.setup_webdriver()

        if not folder.endswith("/"):
            folder += "/"
        if not os.path.exists(PROJECT_PATH + 'visualization/' + folder):
            os.makedirs(PROJECT_PATH + 'visualization/' + folder)

        filepath = PROJECT_PATH + 'visualization/' + folder + filename
        filepath_html = filepath + '.html'
        self.map.save(filepath_html)
        # image resolution
        ratio = 1920 / 1080
        height = 1200 if tall_city else 1080
        width = height * ratio
        webdriver.set_window_size(width, height)
        webdriver.get("file:///" + filepath + '.html')
        time.sleep(0.2)
        webdriver.save_screenshot(filepath + '.png')
        if os.path.exists(filepath_html):
            os.remove(filepath_html)
