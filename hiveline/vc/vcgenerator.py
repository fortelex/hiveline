import random
import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox
import h3.api.numpy_int as h3
from shapely.geometry import Point, LineString
from shapely.ops import transform
from pyproj import Transformer
from .virtualcommuter import VirtualCommuter

from hiveline.od.stats import Stats
from hiveline.od.variables import min_distance_to_take_car


# better random
def rand():
    return random.SystemRandom().random()

def randint(a, b):
    '''
    Random integer in [a,b]
    '''
    return random.SystemRandom().randint(a, b)

def uniform(a,b):
    '''
    Random float in [a,b]
    '''
    return random.SystemRandom().uniform(a,b)

def rand_choice_uniform(events):
    '''
    Randomly selects an element from a list, each element has an equal chance to be chosen
    Args:
        events (list of anything): the events to chose from
    Returns:
        one of the events
    '''
    n = int(randint(0,len(events)-1))
    return events[n]

def rand_choice(events, probabilities):
    '''
    Randomly selects an element from a list, given their probabilities
    Args:
        events (list of anything): the events to chose from
        probabilities (list of float): the associated probabilities (must be in the same order as corresponding events)
    Returns:
        one of the events
    '''
    # sort arrays
    order = np.argsort(probabilities)
    events = [events[i] for i in order]
    probabilities = [probabilities[i] for i in order]
    # get random value
    n = rand()
    cumulated = probabilities[0]
    for i, p in enumerate(probabilities):
        if n <= cumulated:
            return events[i]
        cumulated+=p
    return events[-1]
    
def rand_point_in_polygon(polygon):
    '''
    Randomly selects a point (lat, lon) in a polygon
    Args:
        polygon (shapely polygon): the polygon in which the random point is contained
    Returns:
        (shapely.Point)
    '''
    minx, miny, maxx, maxy = polygon.bounds
    prevent_infinite_loop = 0
    while True and prevent_infinite_loop<100:
        loc = Point(uniform(minx, maxx), uniform(miny, maxy))
        prevent_infinite_loop+=1
        if polygon.contains(loc):
            return loc
    return False

def rand_point_in_linestring(line):
    '''
    Sample a random point in a linestring
    Args:
        line (shapely.LineString): The line to sample from
    Returns:
        (shapely.Point): A random point
    '''
    if len(line.coords)==1: # single point
        return line
    # project the line to processable coordinates
    line = project(line)
    # get a random point in that line
    point = line.interpolate(rand(), normalized=True)
    # project back to epsg 4326
    point = project(point, in_crs="epsg:6933", out_crs="epsg:4326")
    return point

def project(obj, in_crs="epsg:4326", out_crs="epsg:6933"):
    '''
    Project a shapely object (point, line, polygon, etc) to another coordinate reference system (crs)
    Useful for computing distances, areas
    Args: 
        obj (shapely object): the object to project
        in_crs (str): initial crs
        out_crs (str): final crs
    Returns:
         (shapely object): the same object projected to the new crs
    '''
    crs_transformer = Transformer.from_crs(in_crs, out_crs, always_xy=True).transform
    transformed_obj = transform(crs_transformer, obj)
    return transformed_obj

def distance(a,b):
    '''
    Project and compute distance between two points
    Args:
        a, b (shapely.geometry.Point): the points to compute distance
    Returns:
        (float): the distance in meters
    '''
    # distance is 0 if one of the point is not defined
    if not (a and b):
        return 0
    proj_a = project(a)
    proj_b = project(b)
    d = proj_a.distance(proj_b)
    return round(d, 2)

def cut_linestring(line, indexes):
    '''
    Cut a linestring into a smaller one
    Args:
        line (shapely.LineString): the whole line to cut
        indexes (list of int): the list of consecutive indexes to keep
    Returns:
        The shortened linestring, or a point in case a single index is provided
    '''
    if len(indexes)==1:
        return Point(line.coords[indexes[0]])
    
    return LineString(line.coords[indexes[0]:indexes[-1]+1])

def split_list(l):
    '''
    Split a list of ascending integers to sub lists of consecutives ascending integers
    (they might exist more optimal ways to do it)
    Args:
        l (list of integers): the list to split
    Returns:
        (list of lists of integers)
    '''
    new_l = [[]]
    k=0
    ref = l[0]
    for i, e in enumerate(l):
        if e - i != ref:
            new_l.append([])
            k+=1
            ref = e - i
        new_l[k] +=[e]
    return new_l
    
def linestring_length(line):
    '''
    Compute the length of a shapely linestring
    Args:
        line (shapely.LineString): a line
    Returns:
        (float): the line length, in meters
    '''
    # a point is considered of length 1 m (to have later a probability to be selected)
    if len(line.coords)==1:
        return 1
    line = project(line)
    length = round(line.length, 2)
    return length

def linestring_length_gdf(row):
    '''
    Same as linestring_length() but to apply to a GeoDataFrame
    Args:
        row (GeoDataFrame row)
    Returns:
        (float): the line length, in meters
    '''
    return linestring_length(row['geometry'])

class VirtualCommuterGenerator():
    def __init__(self, city):
        '''
        Load zoning and demographic data for a given place
        Args:
            city (Place): the place to study
        '''
        self.city = city
        self.stats = Stats(city)
        self.load_data()
        self.region = None # can change for each vc
        
    def load_data(self):
        self.city.load_all()
        self.stats.load_all()
  
    def get_demo_columns(self, prefix):
        '''
        Get the column names of the demographic dataframe that contains a prefix
        Args:
            prefix (str): the prefix to search
        Return:
            (list of str): the column names
        '''
        cols = [c for c in self.stats.demographic.columns if prefix in c]
        return cols
    
    def get_demo_stat(self, region, stat):
        '''
        Filter demographic dataframe for given region and columns
        Args:
            region (str): the region to filter
            stat (list of str): the columns to filter
        Returns:
            (pd.DataFrame): the filtered dataframe
        '''
        return self.stats.demographic.loc[self.stats.demographic['nuts3']==region, stat]
    
    def get_tile_data(self, tile, columns):
        '''
        Filter tiles data for given tile and columns
        Args:
            tile (int): the tile id to filter
            columns (list of str): the columns to filter
        Returns:
            (pd.DataFrame): the filtered dataframe
        '''
        return self.city.data.loc[self.city.data['h3']==tile, columns]
    
    def rand_point_in_tile(self, tile):
        '''
        Get a random point within a tile
        Args:
            tile (int): the tile id
        Returns:
            (shapely point): a geo point
        '''
        tile_geometry = self.city.tiles.loc[self.city.tiles['h3']==tile, 'geometry']
        tile_geometry = tile_geometry.item()
        loc = rand_point_in_polygon(tile_geometry)
        return loc
    
    def load_roads(self):
        '''
        Get the list of roads or road segments and their associated h3 tile id
        such that each road is within a single tile
        Returns:
            (geopandas.GeoDataFrame)
        '''
        print(f'Loading roads from {self.city.name}...')
        # get the graph of roads except main roads (where no housing along) 
        custom_filter = '["highway"!~"motorway|trunk|primary|secondary|tertiary|escape|raceway|proposed|construction|via_ferrata|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link"]'
        graph = ox.graph_from_place(self.city.name, network_type='all_private', custom_filter=custom_filter)

        # extract only the roads and the needed data
        roads = []
        for u, v, data in graph.edges(data=True):
            keys = data.keys()
            # filter roads where geometry is available
            if ('highway' in keys) and ('geometry' in keys):
                line = data['geometry']
                tiles = {}
                # get the tile id containing each point of the line
                for i, (lon, lat) in enumerate(data['geometry'].coords):
                    point_tile = h3.geo_to_h3(lat, lon, 8)
                    history=tiles.get(point_tile, [])
                    tiles.update({point_tile: history+[i]})
                # store all roads and their corresponding tiles per point
                roads += [{'geometry': line, 'tiles':tiles }]

        # split the roads to have each line (or road) belonging to a single hex tile
        new_roads = []
        for i, r in enumerate(roads):
            tiles = r['tiles'].keys()
            # no change if there is a single tile id for a given road
            if len(tiles)==1:
                new_roads.append({
                    'geometry': r['geometry'],
                    'h3': list(tiles)[0],
                    })
            # otherwise, cut the road into segments per tile
            else:
                for tile in tiles:
                    for indexes in split_list(r['tiles'][tile]):
                        sub_line = cut_linestring(r['geometry'], indexes)
                        new_roads.append({
                            'geometry': sub_line,
                            'h3': tile,
                        })

        # then, put the data (road segments and tile id) in a GeoDataFrame
        roads_gdf = gpd.GeoDataFrame.from_records(new_roads)

        # finally, compute road length and associated probability 
        roads_gdf['length'] = roads_gdf.apply(linestring_length_gdf, axis=1)
        # proba is the road length divided by the total length of roads for the same tile
        total_tile_length = roads_gdf.groupby('h3')['length'].sum().reset_index()
        for i, r in roads_gdf.iterrows():
            total = total_tile_length.loc[total_tile_length['h3']==r['h3'], 'length'].item()
            roads_gdf.loc[i, 'proba'] = r['length']/total
        
        print('Done')
        self.roads_gdf = roads_gdf
        return roads_gdf

    def sample_point_from_roads(self, tile):
        '''
        Get a random point from a random road in a given tile
        '''
        # filter roads belonging to the tile
        roads_gdf_in_tile = self.roads_gdf[self.roads_gdf['h3']==tile]
        roads = roads_gdf_in_tile['geometry'].tolist()
        probas = roads_gdf_in_tile['proba'].tolist()
        # get a random road according to the probas
        rand_road = rand_choice(roads, probas)
        # interpolate a random point in that road
        rand_point = rand_point_in_linestring(rand_road)
        return rand_point

    def generate_origin(self, realistic=False):
        '''
        Generate random origin point
        Random tile according to population distribution, then random point in tile.
        Args:
            realistic (bool): if True, the generated point is along a road
                more realistic but requires to load first roads_gdf, that adds processing time
                advised to set to True only for visualizations
        Returns:
            tile (int): the tile id
            loc (shapely point): a geo point
        '''
        population = self.city.data[['h3', 'population']].copy()
        # convert to percentages
        population['population'] = population['population']/population['population'].sum()
        # get random tile
        tile = rand_choice(population['h3'], population['population'])
        self.region = self.city.data.loc[self.city.data['h3']==tile, 'nuts3'].item()
        # get random point
        if realistic:
            loc = self.sample_point_from_roads(tile)
        else:
            loc = self.rand_point_in_tile(tile) 
        return tile, loc
            
    def generate_variable(self, name):
        '''
        Filter demographic data for a given category expressed in percentages
        Randomly select one of the sub categories, respecting the probabilities
        Args:
            name (str): a category (ex: 'age')
        Returns:
            (str): one of the sub categories
        '''
        var_categories = self.get_demo_columns(name)
        var_df = self.get_demo_stat(self.region, var_categories)
        var_proba = var_df.values.flatten().tolist()
        var = rand_choice(var_categories, var_proba)
        var = var.replace(name+'_','')
        return var
    
    def generate_employment(self, age):
        '''
        Chose if the vc is employed or not
        Args:
            age (str): the age category
        Returns:
            (bool): is employed (True) or not (False)
        '''
        emp_rate_cols = self.get_demo_columns('employment_rate')
        emp_rate_df = self.get_demo_stat(self.region, emp_rate_cols)
        if age == 'under_20':
            employment = False
        else:
            emp_rate = emp_rate_df['employment_rate_'+age].item()
            employment = rand()*100 <= emp_rate
        return employment
    
    def generate_destination(self, age, employment_type, realistic=False):
        '''
        Get a destination point according to the employment and the zoning data
        Args:
            age (str): the age category
            employment_type (str): the employment type category
            realistic (bool): if True, the generated point is along a road
                more realistic but requires to load first roads_gdf, that adds processing time
                advised to set to True only for visualizations
        Returns:
            tile (int): the tile id
            loc (shapely point): a geo point
        '''
        if age == 'under_20':
            interest = 'education'
        elif employment_type:
            interest = 'work_'+employment_type
        else:
            return None, None
        # get random tile with probabilities based on vc interest
        interest_df =  self.city.data[['h3', interest]].copy()
        interest_df[interest] = interest_df[interest]/interest_df[interest].sum()
        tile = rand_choice(interest_df['h3'], interest_df[interest])
        # get random point
        if realistic:
            loc = self.sample_point_from_roads(tile)
        else:
            loc = self.rand_point_in_tile(tile)
        return tile, loc
    
    def vehicle_proba_with_parking(self, vehicle_type, vehicle_proba, origin_tile):
        '''
        Adapt the probability of owning a vehicle with the proba of home parking (based on building density)
        It results in increasing the probability of having a car in suburbs
        The overall car probability in the city remains the same
        Args:
            vehicle_type (str): the type of vehicle ('car' or 'moto')
            vehicle_proba (float): the initial probability of having a vehicle in the region
            origin_tile (int): the origin tile id
        Returns:
            (float): the weighted probability of having a car
        '''
        park_col = 'parking_origin_'+vehicle_type
        city_data = self.city.data[['population', park_col]].copy()
        tile_population = self.get_tile_data(origin_tile, 'population').item()
        tile_parking_home = self.get_tile_data(origin_tile, park_col).item()
        tile_pop_percent =tile_population/city_data['population'].sum()
        tile_park_softmax = np.exp(tile_parking_home)/np.sum(np.exp(city_data[park_col]), axis=0)
        tile_park_weight = tile_park_softmax/tile_pop_percent
        weighted_vehicle_proba = vehicle_proba * tile_park_weight
        return weighted_vehicle_proba


    def generate_vehicle(self, age, vehicle_type, origin_tile, use_parking):
        '''
        Chose if a vc owns a vehicle of a given type
        Args:
            age (str): the age category
            vehicle_type (str): the vehicle category
            use_parking (bool): if true, takes the home parking probability to weight the vehicle ownership localy (per tile)
        Returns:
            (int or None): the count of vehicle of that category
        '''
        prefix = 'vehicle_'
        if age == 'under_20':
            return None
        vehicle_proba = self.get_demo_stat(self.region, prefix+vehicle_type).item()
        if use_parking:
            # weight probability by parking if wanted
            if vehicle_type in ['car', 'moto']:
                vehicle_proba = self.vehicle_proba_with_parking(vehicle_type, vehicle_proba, origin_tile)
        # can have multiple cars
        if vehicle_proba > 1:
            # not perfect, for now more than 2 cars (rare for an average) is giving a random int between 2 and ceil(vehicle_proba) with equal proba
            if vehicle_proba > 2:
                value = randint(2, np.ceil(vehicle_proba))
            # in case the average is between 1 and 2, it can be solved
            else:
                proba_2_cars = vehicle_proba-1
                value = 2 if rand() < proba_2_cars else 1
        # most common case, car per person < 1
        else:
            value = 1 if rand() < vehicle_proba else None
        return value
    
    def generate_vehicle_usage(self, vehicles, distance_to_work, dest_tile, use_parking):
        '''
        Chose if a vs use a vehicle to go to work
        Args:
            vehicles (dict): the owned vehicles
            distance_to_work (float): the distance between origin and destnation, in m
            dest_tile (int): the id to the destination tile
            use_parking (bool): if true, takes the work parking probability to weight the vehicle usage
        Returns:
            (dict): the same dict with an additional field: 'usage'
        '''
        usage = None
        # use a car or moto if the distance is long enough and there is a corresponding parking at workplace
        for v in ['car', 'moto']:
            if vehicles[v]:
                if distance_to_work > min_distance_to_take_car:
                    if use_parking:
                        parking_proba = self.get_tile_data(dest_tile, 'parking_destination_'+v).item()
                    else:
                        parking_proba = 0.9
                    if rand() < parking_proba:
                        usage = v
        # high proba to use a utility vehicle
        if vehicles['utilities']:
            if rand() < 0.95:
                usage = 'utilities' 
        vehicles['usage'] = usage
        return vehicles

    
    def generate_commuter(self, sim_id, use_parking=True, realistic=False):
        '''
        Generate a virtual commuter according to the city demographic and zoning information
        Args:
            sim_id (str): the simulation id containing the vc
            parking (bool): whether or not to take work parking probability into consideration for car usage, and home parking for vehicle ownership
            realistic (bool): if True, the generated point is along a road
                more realistic but more processing time, should not change modal share
                advised to set to True only for visualizations
        Returns:
            (VirtualCommuter): the random vc
        '''
        if realistic:
            self.load_roads()
        origin_tile, origin = self.generate_origin(realistic)
        
        age = self.generate_variable('age')
        employed = self.generate_employment(age)
        employment_type = None
        if employed:
            employment_type = self.generate_variable('employment_type')
        destination_tile, destination = self.generate_destination(age, employment_type, realistic)
        od_distance = distance(origin, destination)
        vehicles = {vehicle_type: self.generate_vehicle(age, vehicle_type, origin_tile, use_parking) for vehicle_type in ['car', 'moto', 'utilities'] }
        vehicles = self.generate_vehicle_usage(vehicles, od_distance, destination_tile, use_parking)

        vc = VirtualCommuter(sim_id, origin_tile, origin, destination_tile, destination, self.region, age, employed, employment_type, vehicles)
        self.region = None
        return vc