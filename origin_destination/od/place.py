import h3.api.numpy_int as h3
import pandas as pd
import geopandas as gpd
import numpy as np
import osmnx as ox
import shapely
import matplotlib.pyplot as plt
from .tags import *
from .variables import data_folder, point_area, default_work_coefficient
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PROJECT_PATH"))
from mongo import mongo


def only_geo_points(gdf):
    '''
    Filters only geo points from a GeoDataFrame
    '''
    return gdf[gdf['geometry'].geom_type == 'Point']


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
        # mongo
        self.mongo_db = mongo.get_database()
        self.load_regions()

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
        if ('geometry' in gdf.columns):
            gdf = gdf.drop(columns='geometry')
        # remove field if already existing
        for field in gdf.drop(columns='h3').columns:
            if field in self.data.columns:
                self.data = self.data.drop(columns=field)
        # merge to data gdf
        self.data = self.data.merge(gdf, on='h3', how='left')

    def mongo_cached(collection, match_field_list, fields, extra_transformation=lambda x:x):
        '''
        Decorator to check if data is available in mongo instead of computing it
        (acts like a cache)
        Args:
            loading_function (function): function that loads data from file, outputs a DataFrame or GeoDataFrame
            collection (str): mongo db collection to search in
            match_field_list (dict): the dataframe field name to match with the mongodb field,  ex: ['nuts3', 'nuts-3']
            fields (list of str): list of fields to retrieve from mongodb
            extra_transformation (function, default is identity): transform the df coming from mongo
        '''
        # 2 wrappers are needed to pass arguments to the decorator
        def wrapper1(loading_function):
            def wrapper2(self): 
                # search fields in mongo, only for place regions
                match_ids = self.data[match_field_list[0]].to_list()
                result_df = mongo.search(self.mongo_db, collection, match_field_list[1], match_ids, fields)
                # call loading function if the search result is empty or incomplete
                if result_df.empty or len(result_df) < len(match_ids):
                    print('Data not in db, computing')
                    data_df = loading_function(self)
                else:
                    print('Data found in db')
                    data_df = extra_transformation(result_df)
                # merge the data to local df
                self.merge_to_data(data_df)
            return wrapper2
        return wrapper1
    
    @mongo_cached(collection='tiles', match_field_list=['nuts3', 'nuts-3'], fields=['population'])
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

        return population_gdf

    def plot_population(self):
        '''
        Plot the shape and the population density overlay
        '''
        if not 'population' in self.data.columns:
            print('loading population data')
            self.load_population()
        ax = self.shape.plot(color='white')
        ax.set_axis_off()
        self.data.plot(ax=ax, zorder=1, column='population')

    def get_zoning(self):
        '''
        Get zoning data from Open Street Map
        '''
        self.zones = {
            'work_agricultural': ox.features_from_place(self.name, work_agricultural_tags),
            'work_industrial': ox.features_from_place(self.name, work_industrial_tags),
            'work_commercial': ox.features_from_place(self.name, work_commercial_tags),
            'work_office': ox.features_from_place(self.name, work_office_tags),
            'work_social': ox.features_from_place(self.name, work_social_tags),
            'education': ox.features_from_place(self.name, education_tags),
            'leisure': ox.features_from_place(self.name, leisure_tags),
            'empty': ox.features_from_place(self.name, empty_tags),
        }

        # keep only points for office as the polygons are badly distributed
        self.zones['work_office'] = only_geo_points(self.zones['work_office'])

    @mongo_cached(collection='tiles', match_field_list=['nuts3', 'nuts-3'], fields=['education', 'leisure', 'empty', 'work'], extra_transformation=mongo.transform_tiles_from_mongo)
    def load_zoning_data(self):
        '''
        Load the zoning data into the data gdf
        Measure the areas of zones of interest (work, education, leisure,...) within each tile
        '''
        self.get_zoning()
        destination = self.tiles.copy()

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
                    nb_points = len(only_geo_points(local_zoi))
                    area = local_zoi.to_crs(epsg=6933).area.sum()
                destination.loc[i, interest] = area + nb_points * point_area
                # default work rate for non empty area, disabled for now
                # if interest == 'empty':
                #    destination.loc[i, 'work'] += (tile_area-area) * \
                #        default_work_coefficient

        # combine all work zones into one
        work_zones = [k for k in self.zones.keys() if 'work' in k]
        destination['work'] = destination[work_zones].sum(axis=1)

        return destination

    @mongo_cached(collection='tiles', match_field_list=['h3', '_id'], fields=['nuts-3'])
    def load_regions(self, nuts_file=data_folder+'nuts/NUTS_RG_01M_2021_4326.geojson'):
        '''
        Get the region of each tile (NUTS 3), and load it to the data
        Args:
            nuts_file (str, default): the geojson file containing the official NUTS European regions
        '''
        nuts = gpd.read_file(nuts_file)
        # keep only the most precise level as it contains the other
        nuts3 = nuts[nuts['LEVL_CODE'] == 3][['id', 'geometry']]
        # nuts regions that overlaps with the city
        place_regions = nuts3.loc[nuts3.overlaps(
            self.shape['geometry'][0]), ['id', 'geometry']]
        place_regions = place_regions.reset_index(drop=True)
        # due to precision differences, the city is overlapping with several regions instead of one
        # regions are defined according to cities boundaries so there should be one region assigned to a city
        # however, a tiled place can span across different regions.
        regions = self.tiles.copy()
        regions['nuts3'] = ''
        # for each tile, compute the intersection area with the regions and keep the largest
        for i, tile in regions.iterrows():
            # check if it intersects before computing the intersection area (otherwise there is a warning)
            intersect = place_regions.intersects(tile['geometry'])
            best_matching_index = place_regions[intersect].intersection(tile['geometry']).to_crs(epsg=6933).area.argmax()
            regions.loc[i, 'nuts3'] = place_regions.iloc[best_matching_index]['id']

        return regions
    
    def load_all(self):
        '''
        Load all the data
        '''
        self.load_population()
        self.load_zoning_data()

    def plot_zoning(self, columns=['population', 'work', 'education', 'leisure'], save_name='filename'):
        '''
        Plot one or several zoning data
        Args:
            columns (list of str): list of columns to plot
            save (str): name of the file to save, the path and city name is automatically added
        '''
        assert len(columns) > 0, 'At least one column is required.'
        for c in columns:
            assert c in self.data.columns, f'The column {c} does not exists in the loaded data.'

        nfig = len(columns)
        ncols = (nfig+1)//2
        nrows = 1 if nfig == 1 else 2
        figsize = (3.5*ncols, 3.5*nrows)

        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize)
        for i, c in enumerate(columns):
            if nfig == 1:
                ax = axes
            elif nfig == 2:
                ax = axes[i % 2]
            else:
                ax = axes[i % 2, i//2]
            # add city boundaries
            self.shape.boundary.plot(ax=ax)
            # add column data
            self.data.plot(ax=ax, column=c)
            ax.set_title(c)
            ax.set_axis_off()

        # don't show axis for last subplot
        if nfig > 1 and nfig % 2 == 1:
            axes[1, ncols-1].set_axis_off()

        # Display the subplots
        fig.suptitle(self.name)
        if save_name:
            city_name = self.name.split(',')[0]
            plt.savefig(
                data_folder+f'visualization/zoning/{save_name}_{city_name}.png', dpi=300)
        plt.show()

    def export_place_to_mongo(self):
        '''
        Push the place data to mongodb
        '''
        n = self.name.split(', ')
        data = [{
            'name': n[0],
            'country': n[1],
            'shape': str(self.shape['geometry'][0]),
            'bbox': str(self.bbox),
            'tiles': self.tiles['h3'].to_list(),
            'nuts-3': self.data['nuts3'].unique().tolist(),
        }]
        mongo.push_to_collection(self.mongo_db, 'places', data)

    def export_tiles_to_mongo(self):
        '''
        Push the tiles and zoning data to mongodb
        '''
        id_df = self.data[['h3', 'nuts3', 'geometry']].copy()
        id_df['geometry'] = id_df['geometry'].astype(str)
        id_df = id_df.rename(columns={'h3': '_id', 'nuts3': 'nuts-3', 'geometry':'shape'})
        data_df = self.data[['population', 'education', 'leisure', 'empty']].copy()
        data_df = pd.concat([id_df, data_df],axis=1)
        data_array = mongo.df_to_dict(data_df)
        prefix = 'work'
        work_df = self.data[[c for c in self.data.columns if prefix in c]].copy()
        work_df = work_df.rename(columns={prefix:'total'})
        work_array = mongo.df_to_dict(work_df)
        # remove prefix
        work_array = [{k.replace(prefix+'_', ''):v for k,v in d.items()} for d in work_array]
        # merge work with other data
        [d.update({'work':work_array[i]}) for i, d in enumerate(data_array)]
        # push
        mongo.push_to_collection(self.mongo_db, 'tiles', data_array)