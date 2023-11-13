import h3.api.numpy_int as h3
import geopandas as gpd
import pandas as pd
import osmnx as ox
import numpy as np
import shapely


class Place():

    def __init__(self, place_name: str):
        self.place_name = place_name
        self.place = ox.geocode_to_gdf(place_name)
        self.bbox = self.place.envelope[0]

    def get_tiles(self, h3_resolution=8):
        """
        Compute H3 tiling and select the tiles matching with the place
        """
        # Create an empty dataframe to write data into
        self.tiles = gpd.GeoDataFrame([], columns=['h3', 'geometry'])
        # Convert multipolygon into list of polygons

        def multi_to_list(multipolygon):
            l = []
            for coords in multipolygon['coordinates']:
                # quick fix, may need to be refined
                if np.ndim(coords) == 3:
                    coords = coords[0]
                list_coords = [[list(x) for x in coords]]
                l.append({
                    'type': 'Polygon',
                    'coordinates': list_coords
                })
            return l

        multipolygon = self.place['geometry'][0]
        # Convert to GeoJSON
        multipoly_geojson = gpd.GeoSeries([multipolygon]).__geo_interface__
        # Parse out geometry key from GeoJSON
        multipoly_geojson = multipoly_geojson['features'][0]['geometry']
        poly_list = multi_to_list(multipoly_geojson)
        for poly_geojson in poly_list:
            # Fill the dictionary with Resolution 8 H3 Hexagons
            h3_hexes = h3.polyfill_geojson(poly_geojson, h3_resolution)
            for h3_hex in h3_hexes:
                h3_geo_boundary = shapely.geometry.Polygon(
                    h3.h3_to_geo_boundary(h3_hex, geo_json=True)
                )
                # Append results to dataframe
                self.tiles.loc[len(self.tiles)] = [
                    h3_hex,
                    h3_geo_boundary,
                ]
        # set coordinates reference system
        if self.tiles.crs == None:
            self.tiles = self.tiles.set_crs(self.place.crs)

    def load_population(self, median_imputation=True, gpkg_path='../data/population_density/kontur_population_20231101.gpkg'):
        """
        Load the population data in a GeoDataFrame
        """
        population_gdf = gpd.read_file(gpkg_path, bbox=self.place)
        # string_to_h3 needed for h3.api.numpy_int (faster)
        population_gdf['h3'] = population_gdf['h3'].apply(h3.string_to_h3)

        self.gdf = population_gdf[population_gdf['h3'].isin(self.tiles['h3'])]
        self.gdf = self.gdf.to_crs(self.place.crs)
        # median imputation for missing values
        if median_imputation:
            no_data = self.tiles[~self.tiles['h3'].isin(self.gdf['h3'])].copy()
            no_data['population'] = self.gdf['population'].median()
            self.gdf = pd.concat([self.gdf, no_data])

    def plot_population(self):
        """
        Plot the place shape and the population density overlay
        """
        ax = self.place.plot(color='white')
        ax.set_axis_off()
        self.gdf.plot(ax=ax, zorder=1, column='population')
