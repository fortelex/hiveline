import pandas as pd
from .variables import *
from hiveline.data.loader import EurostatLoader
from hiveline.data.cleaning import df_to_percent
import hiveline.mongo.db as mongo

class Stats():

    def __init__(self, place):
        '''
        Initialization, create empty DataFrame and list of involved regions
        Args:
            place (Place): a place for which demographic statistics will be computed 
            year (str): the year to study
        '''
        if not 'nuts3' in place.data.columns:
            place.load_regions()
        self.regions = place.data['nuts3'].unique().tolist()
        self.year = place.year
        self.stat_loader = EurostatLoader(year=self.year, nuts_ids=self.regions)
        self.demographic = pd.DataFrame({'nuts3': self.regions})
        # prefixes for categories containing several values
        self.prefixes = ['age', 'vehicle', 'employment_rate', 'employment_type']
        # mongodb database
        self.mongo_db = mongo.get_database()
        self.mongo_collection = 'regions'

    def merge_to_demographic(self, df, precision):
        '''
        Update (or add) a new field to the demographic gdf
        Args:
            df (DataFrame): the gdf to merge, must contains a 'nuts3' column
            precision (int): the nuts precision, 2 or 3
        '''
        # remove field if already existing
        for field in df.drop(columns=f'nuts{precision}').columns:
            if field in self.demographic.columns:
                self.demographic = self.demographic.drop(columns=field)

        # in case of lower resolution (nuts2), duplicates the data for each nuts3 region
        if precision == 2:
            new_df = pd.DataFrame()
            for nuts3_region in self.regions:
                row = df[df['nuts2'] == nuts3_region[:-1]].copy()
                row['nuts2'] = nuts3_region
                new_df = pd.concat([new_df, row])
            new_df = new_df.rename(columns={'nuts2': 'nuts3'})
            df = new_df.copy()

        # merge to data df
        self.demographic = self.demographic.merge(df, on='nuts3', how='left')

    def mongo_cached(fields, collection='regions', match_field_list=['nuts3', '_id'], extra_transformation=mongo.transform_regions_from_mongo):
        '''
        Decorator to check if data is available in mongo instead of computing it
        (acts like a cache)
        Args:
            fields (list of str): list of fields to retrieve from mongodb
            collection (str): mongo db collection to search in
            match_field_list (dict): the dataframe field name to match with the mongodb field,  ex: ['nuts3', 'nuts-3']
            extra_transformation (function): transform the df coming from mongo
            loading_function (function): function that loads data from file, outputs a DataFrame or GeoDataFrame
        '''
        # (almost same as mongo_cached in place.py, later needs to be generalised)
        # 2 wrappers are needed to pass arguments to the decorator
        def wrapper1(loading_function):
            def wrapper2(self): 
                fields_year = [self.year+'.'+f for f in fields]
                # search fields in mongo, only for place regions
                # extract list of region ids
                match_ids = self.demographic[match_field_list[0]].to_list()
                result_df = mongo.search(self.mongo_db, collection, match_field_list[1], match_ids, fields_year)
                # call loading function if the search result is empty or incomplete
                if result_df.empty or len(result_df)!=len(match_ids):
                    print('Data not in db, computing')
                    data_df, precision = loading_function(self)
                else:
                    print('Data found in db')
                    data_df = extra_transformation(result_df)
                    precision = 3
                # merge the data to local df
                self.merge_to_demographic(data_df, precision)
            return wrapper2
        return wrapper1

    @mongo_cached(fields=['age'])
    def load_age(self):
        df = self.stat_loader.get_data('age')
        # convert to percentages
        precision = self.stat_loader.get_precision('age')
        df = df_to_percent(df, f'nuts{precision}') 
        return df, precision
    
    @mongo_cached(fields=['vehicle'])
    def load_motorization(self):
        df_age = self.stat_loader.get_data('age')
        df = self.stat_loader.get_data('vehicle', clean_df_age=df_age)
        precision = self.stat_loader.get_precision('vehicle')
        return df, precision

    @mongo_cached(fields=['employment_rate'])
    def load_employment_rate(self):
        df = self.stat_loader.get_data('employment_rate')
        precision = self.stat_loader.get_precision('employment_rate')
        return df, precision

    @mongo_cached(fields=['employment_type'])
    def load_employment_type(self):
        df = self.stat_loader.get_data('employment_type')
        precision = self.stat_loader.get_precision('employment_type')
        return df, precision

    # @mongo_cached(fields=['income'])
    # def load_income(self):
    #     return df

    def load_all(self):
        '''
        Load all the demographic data
        '''
        # check the data availability
        self.stat_loader.check_all_data()

        self.load_age()
        self.load_motorization()
        self.load_employment_rate()
        self.load_employment_type()
        #self.load_income()
        
        self.export_to_mongo()

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
            }
            # form sub dicts with prefix as key and all field names containing the prefix as values
            subdicts = {p: {k.replace(p+'_',''): v for k,v in d.items() if p in k} for p in self.prefixes}
            formatted.update({self.year: subdicts})
            export_array.append(formatted)

        mongo.push_to_collection(self.mongo_db, self.mongo_collection, export_array)