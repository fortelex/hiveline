import requests
import pandas as pd
from xml.etree import cElementTree as ET
from io import StringIO
from hiveline.data.cleaning import *

datasets = {
    'age': {
        'id': 'demo_r_pjangrp3',
        'precision': 3,
        'parameters': {
            'unit':'NR',
            'sex':'T',
            'age':'Y_LT5,Y5-9,Y10-14,Y15-19,Y20-24,Y25-29,Y30-34,Y35-39,Y40-44,Y45-49,Y50-54,Y55-59,Y60-64,Y65-69,Y70-74,Y75-79,Y80-84,Y85-89,Y_GE90',
        },
        'cleaning_function': clean_age,
    },
    'employment_rate': {
        'id': 'lfst_r_lfe2emprt',
        'precision': 2,
        'parameters': {
            'unit':'PC',
            'sex':'T',
            'age':'Y20-64,Y_GE65',
        },
        'cleaning_function': clean_employment_rate,
    },
    'employment_type': {
        'id': 'nama_10r_3empers',
        'precision': 3,
        'parameters': {
            'unit':'THS',
            'wstatus':'EMP',
            'nace_r2':'A,B-E,F,G-I,J,K,L,M_N,O-Q,R-U',
        },
        'cleaning_function': clean_employment_type,
    },
    'vehicle': {
        'id': 'TRAN_R_VEHST',
        'precision': 2,
        'parameters': {
            'unit':'NR',
            'vehicle':'BUS_TOT,CAR,MOTO,LOR,SPE,TRL_STRL,TRC,UTL,TOT_X_TM',
        },
        'cleaning_function': clean_motorization,
    },
    #'income': {
    #   'id': 'nama_10r_2hhinc',
    #   'precision': 2,
    #   'parameters': {},,
    #   'cleaning_function': clean_income,
    #}
}


class EurostatLoader():
    def __init__(self, nuts_ids, year):
        self.nuts_ids = {
            3: nuts_ids, 
            2: [n[:-1] for n in nuts_ids]
        }
        self.year = year
        self.base_url = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/"
        self.datasets = datasets

    def get_possible_values(self, dataset_id, fields):
        '''
        Load metadata and get the list of possible values for given fields
        Args:
            dataset_id (str): id of the dataset
            fields (list of str): list of the fields to inspect
        Return:
            dict
        '''
        url = self.base_url+"2.1/contentconstraint/ESTAT/"+dataset_id

        # get xml metadata
        r = requests.get(url)
        try:
            xml_root = ET.fromstring(r.text)
        except:
            print(f'Incorrect data, request status code: {r.status_code}')

        # extract namespaces
        namespaces = dict([
            node for _, node in ET.iterparse(
                StringIO(r.text), events=['start-ns']
            )
        ])

        values = {}
        # get the list of possible values for each field
        for field in fields:
            values[field] = []
            keyValue = xml_root.findall(f'm:Structures/s:Constraints/s:ContentConstraint/s:CubeRegion/c:KeyValue[@id="{field}"]', namespaces)
            # extract the value of the `<c:Value>` element within each `<c:KeyValue>` element
            for value in keyValue[0].findall('c:Value', namespaces):
                values[field].append(value.text)
            
        return values
    
    def check_data(self, dataset_id, precision):
        '''
        Check if requested time period and region are available for a given dataset id
        '''
        values = self.get_possible_values(dataset_id, ['TIME_PERIOD', 'geo'])

        # check if requested time is available
        assert self.year in values['TIME_PERIOD'], f'This time period is not available ({self.year} not in {dataset_id}).'
        # check if requested locations are available
        for n in self.nuts_ids[precision]:
            assert n in values['geo'], f'This geographical area is not available ({n} not in {dataset_id}).'

    def check_all_data(self):
        for dataset in self.datasets.values():
            self.check_data(dataset['id'], dataset['precision'])
        print('All data available for these regions and time period')
    
    @staticmethod
    def format_url_parameters(parameters):
        '''
        Format a dict of parameters to url string
        Args:
            parameters (dict)
        Returns:
            str
        '''
        parameters_str = ''
        for key, value in parameters.items():
            parameters_str += f"&c[{key}]={value}"
        return parameters_str
    
    def get_url(self, dataset_id, parameters, precision):
        '''
        Generate an url for a dataset
        Args:
            dataset_id (str): a dataset id
            parameters (dict): the parameters corresponding to dataset filters
            precision (int): the NUTS precision (2 or 3)
        '''
        shared_parameters={
            'freq': 'A',
            'TIME_PERIOD': self.year,
        }

        url = self.base_url+"3.0/data/dataflow/ESTAT/"+dataset_id+"/1.0/*.*.*.*"
        url += ".*" if dataset_id != 'TRAN_R_VEHST' else ''
        url += "?compress=false&format=csvdata&formatVersion=2.0"
        url += self.format_url_parameters(shared_parameters)
        url += self.format_url_parameters(parameters)
        nuts_ids = self.nuts_ids[precision]
        url += self.format_url_parameters({'geo': ','.join(nuts_ids)})
        return url

    def get_data(self, dataset_name, **kwargs):
        # check if data is available before calling this function
        dataset = self.datasets[dataset_name]
        # generate url
        url = self.get_url(dataset['id'], dataset['parameters'], dataset['precision'])
        # try to load the data in a df
        try:
            df = pd.read_csv(url)
        except:
            print('Bad request')

        # clean the data
        df = dataset['cleaning_function'](df, dataset['precision'], **kwargs)

        return df      
    
    def get_precision(self, dataset_name):
        return self.datasets[dataset_name]['precision']