import os

from pymongo import MongoClient
from dotenv import load_dotenv
import pandas as pd

load_dotenv()


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
    db[collection].insert_many(array)

def mongo_to_df(db, collection):
    assert collection in db.list_collection_names(), "This collection doesn't exists"
    df = dict_to_df(db[collection])
    return df

def df_to_mongo(db, collection, df):
    d = df_to_dict(df)
    push_to_collection(db, collection, d)

