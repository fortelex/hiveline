import requests
import pandas as pd
from xml.etree import cElementTree as ET
from io import StringIO

datasets = {
    'age': {
        'id': 'demo_r_pjangrp3',
        'precision': 3,
        'parameters': {
            'unit':'NR',
            'sex':'T',
            'age':'Y_LT5,Y5-9,Y10-14,Y15-19,Y20-24,Y25-29,Y30-34,Y35-39,Y40-44,Y45-49,Y50-54,Y55-59,Y60-64,Y65-69,Y70-74,Y75-79,Y80-84,Y85-89,Y_GE90',
        }
    },
    'employment_rate': {
        'id': 'lfst_r_lfe2emprt',
        'precision': 2,
        'parameters': {
            'unit':'PC',
            'sex':'T',
            'age':'Y20-64,Y_GE65',
        }
    },
    'employment_type': {
        'id': 'nama_10r_3empers',
        'precision': 3,
        'parameters': {
            'unit':'THS',
            'wstatus':'EMP',
            'nace_r2':'A,B-E,F,G-I,J,K,L,M_N,O-Q,R-U',
        }
    },
    'motorization': {
        'id': 'TRAN_R_VEHST',
        'precision': 2,
        'parameters': {
            'unit':'NR',
            'vehicle':'BUS_TOT,CAR,MOTO,LOR,SPE,TRL_STRL,TRC,UTL,TOT_X_TM',
        }
    },
    #'income': {
    #   'id': 'nama_10r_2hhinc',
    #   'precision': 2,
    #   'parameters': {},
    #}
}


class EurostatLoader():
    def __init__(self, year, nuts_ids):
        self.year = year
        self.nuts_ids = {
            3: nuts_ids, 
            2: [n[:-1] for n in nuts_ids]
        }
        self.base_url = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/"
        self.datasets = datasets

    def get_possible_values(self, dataset, fields):
        '''
        Load metadata and get the list of possible values for given fields
        Args:
            dataset (str): id of the dataset
            fields (list of str): list of the fields to inspect
        Return:
            dict
        '''
        url = self.base_url+"2.1/contentconstraint/ESTAT/"+dataset

        # get xml metadata
        r = requests.get(url)
        try:
            root = ET.fromstring(r.text)
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
            keyValue = root.findall(f'm:Structures/s:Constraints/s:ContentConstraint/s:CubeRegion/c:KeyValue[@id="{field}"]', namespaces)
            # Extract the value of the `<c:Value>` element within each `<c:KeyValue>` element
            for value in keyValue[0].findall('c:Value', namespaces):
                values[field].append(value.text)
            
        return values
    
    def check_data(self, dataset, precision):
        '''
        Check if requested time period and region are available for a given dataset
        '''
        values = self.get_possible_values(dataset, ['TIME_PERIOD', 'geo'])

        # check if requested time and location is available
        assert self.year in values['TIME_PERIOD'], f'This time period is not available ({self.year}).'
        for n in self.nuts_ids[precision]:
            assert n in values['geo'], f'This geographical area is not available ({n} not in {dataset}).'
    
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
    
    def get_url(self, dataset, parameters, precision):
        '''
        Generate an url for a dataset
        Args:
            dataset (str): a dataset id
            parameters (dict): the parameters corresponding to dataset filters
            precision (int): the NUTS precision (2 or 3)
        '''
        url = self.base_url+"3.0/data/dataflow/ESTAT/"+dataset+"/1.0/*.*.*.*"
        url += ".*" if dataset != 'TRAN_R_VEHST' else ''
        url += "?compress=false&format=csvdata&formatVersion=2.0"
        url += self.format_url_parameters(parameters)
        nuts_ids = self.nuts_ids[precision]
        url += self.format_url_parameters({'geo': ','.join(nuts_ids)})
        return url

    def get_all_data(self):
        shared_parameters=self.format_url_parameters({
            'freq': 'A',
            'TIME_PERIOD': self.year,
        })

        for dataset in datasets.values():
            self.check_data(dataset['id'], dataset['precision'])
            url = self.get_url(dataset['id'], dataset['parameters'], dataset['precision'])
            url += shared_parameters
            try:
                df = pd.read_csv(url)
                print('ok')
            except:
                print('Bad request')