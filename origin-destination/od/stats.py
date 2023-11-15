import pandas as pd
from .variables import *


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

    def load_data(self, filepath, percentage=False):
        '''
        Load demographic data (cleaned from eurostat)
        Args:
            filepath (str): the path to the csv file
            percentage (bool): whether or not to compute percentages
        '''
        df = pd.read_csv(filepath)
        resolution, regions = self.get_resolution(df)
        # filter df to keep only wanted regions
        df = df[df[resolution].isin(regions)]
        # transform to percentages
        if percentage:
            df = df_to_percent(df, resolution)
        # add the new data
        self.merge_to_demographic(df, resolution)

    def load_age(self, filepath=age_file):
        self.load_data(filepath, percentage=True)

    def load_employment_rate(self, filepath=employment_rate_file):
        self.load_data(filepath)

    def load_employment_type(self, filepath=employment_type_file):
        self.load_data(filepath)

    def load_motorization(self, filepath=motorization_file):
        self.load_data(filepath)

    def load_income(self, filepath=income_file):
        self.load_data(filepath)

    def load_all(self):
        self.load_age()
        self.load_employment_rate()
        self.load_employment_type()
        self.load_motorization()
        self.load_income()
