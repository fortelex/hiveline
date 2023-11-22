import warnings

import folium
import h3
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mpl_colors
import geopandas as gpd
import pandas as pd
from selenium import webdriver
import time
import os
import sys
from dotenv import load_dotenv

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


def style_white(feature):
    return {
        'color': 'white',
        'opacity': 0.6,
        'weight': 3,
    }


class CityPlotter():
    def __init__(self, city, zoom=13):
        self.city = city
        if len(city.data.columns) <= 3:
            self.city.load_all()
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

    def add_city_shape(self):
        shape = self.city.shape.boundary.__geo_interface__
        shape = folium.GeoJson(data=shape, style_function=style_white)
        shape.add_to(self.map)

    def add_hex_heatmap(self, column):
        max_val = self.city.data[column].max()

        # add each tile to the map with the corresponding color
        for _, tile in self.city.data.iterrows():
            geo_j = tile["geometry"].__geo_interface__
            geo_j['color'] = get_mpl_color(tile[column] / max_val)
            geo_j = folium.GeoJson(data=geo_j, style_function=style_heatmap)
            geo_j.add_to(self.map)

    # Convert H3 hexagons to geographic boundaries and create DataFrame
    def __hexagon_to_polygon(self, hexagon):
        boundary = h3.h3_to_geo_boundary(hexagon, True)
        return [[coord[1], coord[0]] for coord in boundary]  # Switch to (lat, long)

    def add_custom_hex_heatmap(self, data):
        """
        Add a custom heatmap to the map. For adding city input data, use add_hex_heatmap instead.
        :param data: a dictionary with the h3 hexagon id as key and the heat value as value
        :return:
        """
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
            ).add_to(self.map)

        # Add color scale legend
        linear.add_to(self.map)

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

    def add_traces(self, traces, max_points_per_trace=None):
        """
        Add traces to the map
        :param traces: list of trace objects. each trace object is a dict with keys: tdf, color where tdf is a
        TrajectoryDataFrame and color is a hex color string
        :param max_points_per_trace: max number of points to plot per trace
        :return:
        """
        # ignore warning about down-sampling
        warnings.filterwarnings('ignore', 'If necessary, trajectories will be down-sampled', UserWarning)
        for trace in traces:
            tdf = trace["tdf"]
            color = trace["color"]
            # need to plot each trace separately to be able to set the color
            self.map = tdf.plot_trajectory(map_f=self.map, start_end_markers=False, max_users=1,
                                           max_points=max_points_per_trace,
                                           hex_color=color)

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
