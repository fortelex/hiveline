import pandas as pd
import inspect
from .variables import *
import os
import sys
from dotenv import load_dotenv
load_dotenv()
# add an environment variable storing the file path to the current project directory
sys.path.append(os.getenv("PROJECT_PATH"))
from mongo import mongo

def df_to_percent(df, index):
    '''
    Replace values by percentages per row
    Args:
        df (DataFrame): the dataframe to transform
        index (str): the name of the column to consider as index
    Returns:
        the same dataframe with values in percentages 
    '''
    df = df.set_index(index)
    df = df.div(df.sum(axis=1), axis=0)
    return df.reset_index()


class Stats():

    def __init__(self, place):
        '''
        Initialization, create empty DataFrame and list of involved regions
        Args:
            place (Place): a place for which demogrphic statistics will be computed 
        '''
        if not 'nuts3' in place.data.columns:
            place.load_regions()
        self.regions = place.data['nuts3'].unique().tolist()
        self.demographic = pd.DataFrame({'nuts3': self.regions})
        # prefixes for categories containing several values
        self.prefixes = ['age', 'vehicle', 'employment_rate', 'employment_type']
        # mongodb database
        self.mongo_db = mongo.get_database()
        self.mongo_collection = 'regions'

    def merge_to_demographic(self, df, resolution):
        '''
        Update (or add) a new field to the demographic gdf
        Args:
            df (DataFrame): the gdf to merge, must contains a 'nuts3' column
        '''
        # remove field if already existing
        for field in df.drop(columns=resolution).columns:
            if field in self.demographic.columns:
                self.demographic = self.demographic.drop(columns=field)

        # in case of lower resolution (nuts2), duplicates the data for each nuts3 region
        if resolution == 'nuts2':
            new_df = pd.DataFrame()
            for nuts3_region in self.regions:
                row = df[df['nuts2'] == nuts3_region[:-1]].copy()
                row['nuts2'] = nuts3_region
                new_df = pd.concat([new_df, row])
            new_df = new_df.rename(columns={'nuts2': 'nuts3'})
            df = new_df.copy()

        # merge to data df
        self.demographic = self.demographic.merge(df, on='nuts3', how='left')

    def get_resolution(self, df):
        '''
        Get the geo resolution level of the given data
        Args:
            df (DataFrame): the dataframe to inspect
        Returns:
            str: nuts resolution
            list of str: list of regions ids to consider
        '''
        if 'nuts3' in df.columns:
            return 'nuts3', self.regions
        elif 'nuts2' in df.columns:
            return 'nuts2', [r[:-1] for r in self.regions]
        else:
            raise Exception(
                'The dataframe should contains a nuts2 or nuts3 column')

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
        # (almost same as mongo_cached in place.py, later needs to be generalised)
        # 2 wrappers are needed to pass arguments to the decorator
        def wrapper1(loading_function):
            def wrapper2(self): 
                # search fields in mongo, only for place regions
                match_ids = self.demographic[match_field_list[0]].to_list()
                result_df = mongo.search(self.mongo_db, collection, match_field_list[1], match_ids, fields)
                # call loading function if the search result is empty or incomplete
                if result_df.empty or len(result_df)!=len(match_ids):
                    print('Data not in db, computing')
                    data_df, resolution = loading_function(self)
                else:
                    print('Data found in db')
                    data_df = extra_transformation(result_df)
                    resolution = 'nuts3'
                # merge the data to local df
                self.merge_to_demographic(data_df, resolution)
            return wrapper2
        return wrapper1

    def loader(filepath):
        '''
        Decorator to load demographic data (cleaned from eurostat)
        The decorated function is adding transformation before merging
        Args:
            transformation (function): the decorated function that transforms the data (DataFrame in, DataFrmae out)
            filepath (str): the path to the csv file
        '''
        # 2 wrappers are needed to pass arguments to the loader
        def wrapper1(transformation):
            def wrapper2(self): 
                df = pd.read_csv(filepath)
                resolution, regions = self.get_resolution(df)
                # filter df to keep only wanted regions
                df = df[df[resolution].isin(regions)]
                # specific transformation if needed 
                kwargs = {'resolution': resolution} if 'resolution' in inspect.getfullargspec(transformation).args else {}
                df = transformation(self, df, **kwargs)
                # return the new data
                return df, resolution
            return wrapper2
        return wrapper1

    @mongo_cached(collection='regions', match_field_list=['nuts3', '_id'], fields=['age'], extra_transformation=mongo.transform_regions_from_mongo)
    @loader(filepath=age_file)
    def load_age(self, df, resolution=None):
        # convert to percentages
        df = df_to_percent(df, resolution) 
        return df
    
    @mongo_cached(collection='regions', match_field_list=['nuts3', '_id'], fields=['vehicle'], extra_transformation=mongo.transform_regions_from_mongo)
    @loader(filepath=motorization_file)
    def load_motorization(self, df):
        return df

    @mongo_cached(collection='regions', match_field_list=['nuts3', '_id'], fields=['income'], extra_transformation=mongo.transform_regions_from_mongo)
    @loader(filepath=income_file)
    def load_income(self, df):
        return df

    @mongo_cached(collection='regions', match_field_list=['nuts3', '_id'], fields=['employment_rate'], extra_transformation=mongo.transform_regions_from_mongo)
    @loader(filepath=employment_rate_file)
    def load_employment_rate(self, df):
        return df

    @mongo_cached(collection='regions', match_field_list=['nuts3', '_id'], fields=['employment_type'], extra_transformation=mongo.transform_regions_from_mongo)
    @loader(filepath=employment_type_file)
    def load_employment_type(self, df):
        # regroup types
        df['agricultural'] = df['Agriculture']
        df['industrial'] = df['Industry'] + df['Construction']
        df['commercial'] = df['Wholesale, retail trade, transport, accomodation and food service'] + df['Real estate'] + df['Arts, entertainment, other service']
        df['office'] = df['Information and communication'] + df['Finance, insurance'] + df['Professional, scientific and technical, administrative']
        df['social'] = df['Public administration, defence, education, health, social']
        df = df[['nuts3', 'agricultural', 'industrial', 'commercial', 'office', 'social']]
        # add prefix
        df = df.rename(columns={c: 'employment_type_'+c if c != 'nuts3'else c for c in df.columns})
        return df

    def load_all(self):
        '''
        Load all the demographic data
        '''
        self.load_age()
        self.load_motorization()
        self.load_income()
        self.load_employment_rate()
        self.load_employment_type()

    def export_to_mongo(self):
        '''
        Transform the demographic dataframe and push it to mongodb
        '''
        df_array = mongo.df_to_dict(self.demographic)
        export_array = []
        # transform the list of dict
        for d in df_array:
            formatted = {
                '_id': d['nuts3'],
                'income': d['household_income'],
            }
            # form sub dicts with prefix as key and all field names containing the prefix as values
            subdicts = {p: {k.replace(p+'_',''): v for k,v in d.items() if p in k} for p in self.prefixes}
            formatted.update(subdicts)
            export_array.append(formatted)

        mongo.push_to_collection(self.mongo_db, self.mongo_collection, export_array)