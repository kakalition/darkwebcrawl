import os
from config import (
    MONGO_HOST,
    MONGO_PASS,
    MONGO_PORT,
    MONGO_USER,
)

try:
    from pymongo import MongoClient
except ImportError:
    raise ImportError('PyMongo is not installed in your machine.')

class MongoDBClient:
    def __init__(
        self,
        host=MONGO_HOST,
        port=MONGO_PORT,
        username=MONGO_USER,
        password=MONGO_PASS,
        database_name="crawler",
    ):
        self.client = client = MongoClient(f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}?directConnection=true")
        self.database = self.client[database_name]

    def upsert_document(self, collection_name, document, query):
        collection = self.database[collection_name]
        collection.update_one(query, {"$set": document}, upsert=True)

    def find_document(self, collection_name, query, distinct_field=None):
        collection = self.database[collection_name]
        return collection.find(query).distinct(distinct_field)

    def find_one(self, collection_name, *args):
        collection = self.database[collection_name]
        return collection.find_one(*args)
