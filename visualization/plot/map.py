import folium
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mpl_colors
import geopandas as gpd
from selenium import webdriver
import time
import os
import sys
from dotenv import load_dotenv
load_dotenv()
PROJECT_PATH = os.getenv("PROJECT_PATH")
sys.path.append(PROJECT_PATH)

def get_mpl_color(value, colormap_name='magma'):
    colormap = cm.get_cmap(colormap_name)
    color = colormap(value)
    color = mpl_colors.rgb2hex(color)
    return color

def style_heatmap(feature):
    return {
        'fillColor': feature['geometry']['color'],
        'color': 'black',#  # Set the border color 
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
        self.centroid = self.get_centroid()#[48.857003, 2.3492646]
        self.map = self.get_map(zoom)

    def get_centroid(self):
        c = self.city.shape.centroid
        return [c.y, c.x]

    def get_map(self, zoom, dark = True):
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
            geo_j['color'] = get_mpl_color(tile[column]/max_val)
            geo_j = folium.GeoJson(data=geo_j, style_function=style_heatmap)
            geo_j.add_to(self.map)

    def show_map(self):
        return display(self.map)

    def export_to_png(self, folder='images/', filename='image', tall_city=False):
        filepath = PROJECT_PATH+'visualization/'+folder+filename
        filepath_html = filepath+'.html'
        self.map.save(filepath_html)
        options = webdriver.ChromeOptions()
        # do not show chrome 
        options.add_argument("--headless")
        driver = webdriver.Chrome(options=options)
        # image resolution
        ratio = 1920/1080
        height = 1200 if tall_city else 1080
        width = height*ratio
        driver.set_window_size(width, height)
        driver.get("file://"+filepath+'.html')
        time.sleep(2)
        driver.save_screenshot(filepath+'.png')
        if os.path.exists(filepath_html):
            os.remove(filepath_html)
