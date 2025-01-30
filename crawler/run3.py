import argparse
import importlib
import logging
import os
import sys
import traceback
import csv
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import pytz

from config import SITES, PROFILES

from config import (
    MONGO_USER,
    MONGO_PASS,
    MONGO_HOST,
    MONGO_PORT,
)

jakarta_tz = pytz.timezone('Asia/Jakarta')
client = MongoClient(f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}?directConnection=true")
db = client['allnewdarkweb']
collection = db['jobs_crawler']

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)

def run_site(site_name, urls, idpost, userid):
    try:
        # Set up path and import crawler module
        dir_path = os.path.dirname(os.path.realpath(__file__))
        src_path = os.path.join(dir_path, "src")
        sys.path.append(src_path)
        module = importlib.import_module(site_name)

        # Initialize and run crawler
        crawler_class = getattr(module, "DarkwebCrawler")
        crawler_instance = crawler_class()
        result_count = crawler_instance.run(urls, idpost)

        try:
            # Check if document exists
            document = collection.find_one({"_id": ObjectId(idpost)})

            if document:
                # Determine action type based on site name
                action_type = "profile" if len(site_name.split("_")) > 1 else "crawling"
                current_time = datetime.now(jakarta_tz)

                if action_type == "crawling":
                    # Update for crawling action
                    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
                    update_result = collection.update_one(
                        {"_id": ObjectId(idpost)},
                        {
                            "$set": {
                                "status": '1',
                                "send_post_summary": True,
                                "total_post_real": result_count,
                                "finish_date_post": formatted_time,
                                "user_id": userid
                            }
                        }
                    )
                else:
                    # Update for profile action
                    formatted_time_profile = current_time.strftime("%Y-%m-%d %H:%M:%S")
                    update_result = collection.update_one(
                        {"_id": ObjectId(idpost)},
                        {
                            "$set": {
                                "status": '2',
                                "send_profile_summary": True,
                                "total_profile_real": result_count,
                                "finish_date_profile": formatted_time_profile,
                                "user_id_profile": userid
                            }
                        }
                    )

                print("Document updated successfully" if update_result.matched_count > 0 
                      else "No document found to update")
            else:
                print("No document found with the given _id")

        except Exception as e:
            print(f"Error updating document: {e}")
            
    except ModuleNotFoundError:
        logging.error(f"Module {site_name} not found.")
    except AttributeError:
        logging.error(f"DarkwebCrawler class not found in {site_name} module.")
        logging.error(traceback.format_exc())

def main():
    parser = argparse.ArgumentParser(description="Web crawler for various sites.")
    parser.add_argument("--sites", help="http://xxxxx.com")
    parser.add_argument("--name", help="breach example of name site")
    parser.add_argument("--idpost", help="breach example of name site")
    parser.add_argument("--userid", help="breach example of name site")
    
    args = parser.parse_args()

    print(f"Running crawler for name: {args.name} url: {args.sites} idpost: {args.idpost}")
    run_site(args.name, args.sites, args.idpost, args.userid)
    
if __name__ == "__main__":
    main()