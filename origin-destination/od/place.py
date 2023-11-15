import h3.api.numpy_int as h3
import pandas as pd
import geopandas as gpd
import numpy as np
import osmnx as ox
import shapely

from .tags import work_tags, education_tags, leisure_tags, empty_tags
from .variables import data_folder


class Place():

    def __init__(self, place_name: str):
        '''
        Initialize the place object, load geographical shape and tiling
        Args:
            place_name (str): the place name (ex: 'Konstanz, Germany')
        '''
        self.name = place_name
        self.shape = ox.geocode_to_gdf(self.name)
        self.bbox = self.shape.envelope[0]
        self.get_tiles()
        # this GeoDataFrame will store the origin destination stats
        self.data = self.tiles.copy()

    def get_tiles(self, h3_resolution=8):
        '''
        Compute H3 tiling and select the tiles covering the place shape
        Args:
            h3_resolution (int, default=8): tiling resolution
        '''
        # Create an empty dataframe to write data into
        self.tiles = gpd.GeoDataFrame([], columns=['h3', 'geometry'])
        # Convert multipolygon into list of polygons

        def multi_to_list(multipolygon):
            '''
            Convert a multipolygon to a list of polygons
            '''
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

        multipolygon = self.shape['geometry'][0]
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
            self.tiles = self.tiles.set_crs(self.shape.crs)

    def merge_to_data(self, gdf):
        '''
        Update (or add) a new field to the data gdf
        Args:
            gdf (GeoDataFrame): the gdf to merge, must contains an 'h3' column
        '''
        gdf = gdf.drop(columns='geometry')
        # remove field if already existing
        for field in gdf.drop(columns='h3').columns:
            if field in self.data.columns:
                self.data = self.data.drop(columns=field)
        # merge to data gdf
        self.data = self.data.merge(gdf, on='h3', how='left')

    def load_population(self, median_imputation=True, gpkg_path=data_folder+'population_density/kontur_population_20231101.gpkg'):
        '''
        Load the population data in a GeoDataFrame and add it to self.data
        Args:
            median_imputation (boolean, default=True): whether or not to replace missing values with the median
            gpkg_path (str, default): the path to the gpkg data
        '''
        population_gdf = gpd.read_file(gpkg_path, bbox=self.shape)
        # string_to_h3 needed for h3.api.numpy_int (faster)
        population_gdf['h3'] = population_gdf['h3'].apply(h3.string_to_h3)

        population_gdf = population_gdf[population_gdf['h3'].isin(
            self.tiles['h3'])]
        population_gdf = population_gdf.to_crs(self.shape.crs)

        # median imputation for missing values
        if median_imputation:
            no_data = self.tiles[~self.tiles['h3'].isin(
                population_gdf['h3'])].copy()
            no_data['population'] = population_gdf['population'].median()
            population_gdf = pd.concat([population_gdf, no_data])

        self.merge_to_data(population_gdf)

    def plot_population(self):
        '''
        Plot the shape and the population density overlay
        '''
        ax = self.shape.plot(color='white')
        ax.set_axis_off()
        self.gdf.plot(ax=ax, zorder=1, column='population')

    def get_zoning(self):
        '''
        Get zoning data from Open Street Map
        '''
        self.zones = {
            'work': ox.features_from_place(self.name, work_tags),
            'education': ox.features_from_place(self.name, education_tags),
            'leisure': ox.features_from_place(self.name, leisure_tags),
            'empty': ox.features_from_place(self.name, empty_tags),
        }

    def load_zoning_data(self):
        '''
        Load the zoning data into the data gdf
        Measure the areas of zones of interest (work, education, leisure,...) within each tile
        '''
        self.get_zoning()
        destination = self.tiles.copy()
        # replace points (a store for example) by this area value
        point_area = 100  # m²
        # non empty places are accounted as workplaces according to that coefficient
        default_work_coefficient = 0.3
        # area of a whole single hexagonal tile
        tile_area = self.tiles.to_crs(epsg=6933)['geometry'][0].area

        for i, tile in destination.iterrows():
            for interest in self.zones.keys():
                # clip zones by hex tile
                local_zoi = gpd.clip(
                    self.zones[interest], tile['geometry']).copy()  # zoi = zones of interest
                # compute interest area in tile
                area = 0
                nb_points = 0
                if len(local_zoi) != 0:
                    # replace single points with a defined area
                    nb_points = len(
                        local_zoi[local_zoi['geometry'].geom_type == 'Point'])
                    area = local_zoi.to_crs(epsg=6933).area.sum()
                destination.loc[i, interest] = area + nb_points * point_area
                if interest == 'empty':
                    destination.loc[i, 'work'] += (tile_area-area) * \
                        default_work_coefficient

        self.merge_to_data(destination)

    def load_regions(self, nuts_file=data_folder+'nuts/NUTS_RG_01M_2021_4326.geojson'):
        '''
        Get the region of each tile (NUTS 3), and load it to the data
        Args:
            nuts_file (str, default): the geojson file containing the official NUTS European regions
        '''
        nuts = gpd.read_file(data_folder+'nuts/NUTS_RG_01M_2021_4326.geojson')
        # keep only the most precise level as it contains the other
        nuts3 = nuts[nuts['LEVL_CODE'] == 3][['id', 'geometry']]
        # nuts regions that overlaps with the city
        place_regions = nuts3.loc[nuts3.overlaps(
            self.shape['geometry'][0]), ['id', 'geometry']]
        place_regions = place_regions.reset_index()
        # due to precision differences, the city is overlapping with several regions instead of one
        # regions are defined according to cities boundaries so there should be one region assigned to a city
        # however, a tiled place can span across different regions.
        regions = self.tiles.copy()
        regions['nuts3'] = ''
        # for each tile, compute the intersection area with the regions and keep the largest
        for i, tile in regions.iterrows():
            best_matching_index = place_regions.intersection(
                tile['geometry']).to_crs(epsg=6933).area.argmax()
            regions.loc[i, 'nuts3'] = place_regions.iloc[best_matching_index]['id']

        self.merge_to_data(regions)
