import os

import pytz

try:
    from bson.codec_options import CodecOptions
    from pymongo import MongoClient
except ImportError:
    raise ImportError("PyMongo is not installed in your machine.")


class MongoDB(object):
    def __init__(
        self,
        dbname=None,
        collname=None,
        host=os.environ["MONGO_HOST"],
        port=int(os.environ["MONGO_PORT"]),
        username=os.environ["MONGO_USER"],
        password=os.environ["MONGO_PASS"],
        drop_n_create=False,
    ):
        try:
            # creating connection while object creation
            self._connection = MongoClient(
                host=host,
                port=port,
                username=username,
                password=password,
                maxPoolSize=200,
            )
        except Exception as error:
            raise Exception(error)

        # drop database and create new one (optional)
        if drop_n_create:
            self.drop_db(dbname)

        self._database = None
        self._collection = None
        # assigning database name while object creation
        if dbname:
            self._database = self._connection[dbname]
        # assigning collection name while object creation
        if collname:
            self._collection = self._database[collname]

    def __del__(self):
        try:
            self._connection.close()
        except Exception as e:
            print(f" [model.mongodb] {e}")

    @staticmethod
    def check_state(obj):
        if not obj:
            return False
        else:
            return True

    def check_db(self):
        # validate the database name
        if not self.check_state(self._database):
            raise ValueError("Database is empty/not created.")

    def check_collection(self):
        # validate the collection name
        if not self.check_state(self._collection):
            raise ValueError("Collection is empty/not created.")

    def get_overall_details(self):
        # get overall connection information
        client = self._connection
        details = dict(
            (db, [collection for collection in client[db].collnames()])
            for db in client.dbnames()
        )
        return details

    def get_current_status(self):
        # get current connection information
        return {
            "connection": self._connection,
            "database": self._database,
            "collection": self._collection,
        }

    def create_db(self, dbname=None):
        # create the database name
        self._database = self._connection[dbname]

    def create_collection(self, collname=None):
        # create the collection name
        self.check_db()
        self._collection = self._database[collname]

    def get_dbnames(self):
        # get the database name you are currently connected too
        return self._connection.dbnames()

    def get_collnames(self):
        # get the collection name you are currently connected too
        self.check_collection()
        return self._database.collnames(include_system_collections=False)

    def drop_db(self, dbname):
        # drop/delete whole database
        self._database = None
        self._collection = None
        return self._connection.drop_database(str(dbname))

    def drop_collection(self):
        # drop/delete a collection
        self._collection.drop()
        self._collection = None

    def insert(self, post):
        # add/append/new single record
        self.check_collection()
        post_id = self._collection.insert_one(post).inserted_id
        return post_id

    def insert_many(self, posts):
        # add/append/new multiple records
        self.check_collection()
        result = self._collection.insert_many(posts)
        return result.inserted_ids

    def find_one(self, *args, count=False):
        # search/find many matching records returns iterator object
        self.check_collection()
        if not count:
            return self._collection.with_options(
                codec_options=CodecOptions(
                    tz_aware=True, tzinfo=pytz.timezone("Asia/Jakarta")
                )
            ).find_one(*args)
        # return only count
        return self._collection.find(*args).count()

    def find(self, *args, count=False):
        # search/find many matching records returns iterator object
        self.check_collection()
        if not count:
            return self._collection.with_options(
                codec_options=CodecOptions(
                    tz_aware=True, tzinfo=pytz.timezone("Asia/Jakarta")
                )
            ).find(*args)
        # return only count
        return self._collection.find(*args).count()

    def count(self):
        # get the records count in collection
        self.check_collection()
        return self._collection.count()

    def count_documents(self, *args):
        # get the records count in collection
        self.check_collection()
        return self._collection.count(*args)

    def remove(self, *args):
        # remove/delete records
        return self._collection.remove(*args)

    def update(self, *args):
        # updating/modifying the records
        return self._collection.update(*args)

    def upsert(self, *args):
        # updating/modifying the records
        return self._collection.update(*args, upsert=True)

    def aggregate(self, *args):
        # grouping the records
        return self._collection.aggregate(*args)

    def watch(self, *args):
        return self._collection.watch(*args)
