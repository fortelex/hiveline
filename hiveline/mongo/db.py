import os

import pandas as pd
from pymongo import MongoClient, UpdateOne


def get_database():
    user = os.getenv("UP_MONGO_USER")
    password = os.getenv("UP_MONGO_PASSWORD")
    domain = os.getenv("UP_MONGO_DOMAIN")
    database = os.getenv("UP_MONGO_DATABASE")

    connection_string = "mongodb://%s:%s@%s/%s?authSource=admin" % (user, password, domain, database)

    client = MongoClient(connection_string)

    return client[database]


def dict_to_df(dictionnary):
    df = pd.DataFrame(dictionnary.find({}))
    return df


def df_to_dict(df):
    return df.to_dict('records')


def push_to_collection(db, collection, array):
    """
    Upserts many documents in a collection
    :param db: the database
    :param collection: the collection
    :param array: the documents to upsert (need _id)
    :return:
    """
    operations = [
        UpdateOne({'_id': doc['_id']}, {'$set': {
            k: v for k, v in doc.items() if k != '_id'
        }}, upsert=True) for doc in array
    ]

    db[collection].bulk_write(operations)


def mongo_to_df(db, collection):
    assert collection in db.list_collection_names(), "This collection doesn't exists"
    df = dict_to_df(db[collection])
    return df


def df_to_mongo(db, collection, df):
    d = df_to_dict(df)
    push_to_collection(db, collection, d)

def is_number(string):
    # checks if a string is composed of digits
    return all(char.isdigit() for char in string)

def transform_from_mongo_extract_year(df):
    # get the year field
    year = [c for c in df.columns if is_number(c)][0]
    # extract everything inside the year field 
    df = pd.concat([df, pd.DataFrame.from_records(df[year].to_list())], axis=1)
    df = df.drop(columns=year)
    return df

def transform_tiles_from_mongo(df):
    '''
    Transform the tiles zoning data from mongodb to convert it back to a dataframe
    Args:
        df (pd.DataFrame): the df coming directly from mongo, that needs to be transformed
    '''
    df = transform_from_mongo_extract_year(df)
    if 'work' in df.columns:
        prefix = 'work'
    elif 'parking' in df.columns:
        prefix = 'parking'
    # extract work sub dict to df
    df = pd.concat([df, pd.DataFrame.from_records(df[prefix].to_list()).add_prefix(prefix + '_')], axis=1)
    df = df.drop(columns=prefix)
    df = df.rename(columns={'_id': 'h3', 'nuts-3': 'nuts3', 'shape': 'geometry'})
    if prefix == 'work':
        df = df.rename(columns={'work_total': 'work'})
    return df


def transform_regions_from_mongo(df):
    '''
    Transform the demographic data from mongodb to convert it back to a dataframe
    '''
    df = transform_from_mongo_extract_year(df)
    prefixes = [c for c in df.columns if c in ['age', 'vehicle', 'employment_rate', 'employment_type']]
    # extract the sub dicts
    df = pd.concat([df] + [pd.DataFrame.from_records(df[p].to_list()).add_prefix(p + '_') for p in prefixes], axis=1)
    df = df.drop(columns=prefixes)
    df = df.rename(columns={'_id': 'nuts3'})
    return df


def search(db, collection, match_field, match_ids, fields):
    '''
    Search if the region_ids are in the db and returns the values for given fields
    Args:
        collection (str): name of the mongo collection
        match_field (str): the mongo field name to match from (ex: 'nuts-3')
        match_ids (list of str): list of ids to match (ex: region ids)
        fields (list of str): list of the names of the collection field to retrieve
    Returns:
        pd.DataFrame
    '''
    if collection == 'tiles':
        match_dict = {
            'nuts-3': 'nuts3',
            '_id': 'h3',
        }
    elif collection == 'regions':
        match_dict = {
            '_id': 'nuts3',
        }

    fields_query = {f: 1 for f in fields}
    result = db[collection].find({match_field: {'$in': match_ids}}, fields_query)
    df = pd.DataFrame.from_records(result)
    df = df.rename(columns=match_dict)
    return df


def get_place_id(db, place_name):
    name, country = place_name.split(', ')
    place_id = db['places'].find({'name': name, 'country': country}, {'_id': 1})
    place_id = place_id[0]['_id']
    return place_id
