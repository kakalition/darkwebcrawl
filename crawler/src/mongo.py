import os


try:
    from pymongo import MongoClient
except ImportError:
    raise ImportError('PyMongo is not installed in your machine.')

class MongoDBClient:
    def __init__(
        self,
        host=os.environ["MONGO_HOST"],
        port=int(os.environ["MONGO_PORT"]),
        username=os.environ["MONGO_USER"],
        password=os.environ["MONGO_PASS"],
        database_name="crawler",
    ):
        self.client = MongoClient(
            host=host,
            port=port,
            username=username,
            password=password,
            authSource=database_name,
            directConnection=True
        )
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
