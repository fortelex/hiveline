import os

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()


def get_database():
    user = os.getenv("UP_MONGO_USER")
    password = os.getenv("UP_MONGO_PASSWORD")
    domain = os.getenv("UP_MONGO_DOMAIN")
    database = os.getenv("UP_MONGO_DATABASE")

    connection_string = "mongodb://%s:%s@%s/%s?authSource=admin" % (user, password, domain, database)

    client = MongoClient(connection_string)

    return client[database]

