import csv
import os
import subprocess
import sys
import bson
import bson.objectid
from pymongo import MongoClient
import argparse
from datetime import datetime
import pytz
import time

from config import (
    MONGO_HOST,
    MONGO_PORT,
)

jakarta_tz = pytz.timezone('Asia/Jakarta')

# Initialize MongoDB Client
client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db = client['darkweb_task']
collection = db['jobs_crawler']

def get_oldest_site():
    """Get the site name with the oldest unprocessed record"""
    # For posts (status "0")
    oldest_post = collection.find_one(
        {"status": "0", "completed": {"$ne": True}},
        sort=[("created_date", 1)]
    )
    
    # For profiles (status "1")
    oldest_profile = collection.find_one(
        {"status": "1"},
        sort=[("created_date", 1)]
    )
    
    if oldest_post and oldest_profile:
        if oldest_post.get('created_date', datetime.max) < oldest_profile.get('created_date', datetime.max):
            return oldest_post['name_site']
        return oldest_profile['name_site']
    elif oldest_post:
        return oldest_post['name_site']
    elif oldest_profile:
        return oldest_profile['name_site']
    return None

def get_next_record(action_type, userid, site=None):
    """Get next unprocessed record"""
    query = {}
    if action_type == "update_posts":
        query["status"] = "0"
        query["completed"] = {"$ne": True}
    else:  # update_profiles
        query["status"] = "1"
    
    if site:
        query["name_site"] = site
    
    # Atomic update to mark as processing
    record = collection.find_one_and_update(
        query,
        {
            "$set": {
                "status": "3",  # Temporary status during processing
                "user_id": userid
            }
        },
        sort=[("created_date", 1)],
        return_document=True
    )
    
    return record

def process_record(record, action_type, userid):
    """Process a single record"""
    try:
        name_site = record['name_site']
        urlpost = record['url']
        idpost = record['_id']
        
        name_param = f"{name_site}_profile" if action_type == "update_profiles" else name_site
        print(f"Processing {action_type} for {name_site}, ID: {idpost}")

        result = subprocess.run(
            ["python", "run3.py", 
             "--sites", urlpost,
             '--name', name_param,
             '--idpost', str(idpost),
             '--userid', userid],
            text=True,
            env=os.environ.copy()
        )
        
        if result.returncode == 0:
            print(f"Successfully processed {idpost} for site: {name_site}")
            new_status = "2" if action_type == "update_profiles" else "1"
            collection.update_one({"_id": idpost}, {"$set": {"status": new_status}})
            return True
        else:
            print(f"Error processing {idpost} for site: {name_site}")
            new_status = "1" if action_type == "update_profiles" else "0"
            collection.update_one({"_id": idpost}, {"$set": {"status": new_status}})
            return False
            
    except Exception as e:
        print(f"Error processing record {idpost}: {str(e)}")
        new_status = "1" if action_type == "update_profiles" else "0"
        collection.update_one({"_id": idpost}, {"$set": {"status": new_status}})
        return False

def process_continuously(action_type, userid, site=None):
    """Process records continuously until none remain"""
    total_processed = 0
    consecutive_empty = 0
    
    while True:
        record = get_next_record(action_type, userid, site)
        
        if not record:
            consecutive_empty += 1
            if consecutive_empty >= 3:  # Check 3 times before giving up
                break
            time.sleep(1)  # Wait a bit before checking again
            continue
            
        consecutive_empty = 0
        success = process_record(record, action_type, userid)
        if success:
            total_processed += 1
        
        # Optional: Add a small delay to prevent overwhelming the system
        time.sleep(0.1)
    
    print(f"\nFinished processing. Total records successfully processed: {total_processed}")
    return total_processed

def import_csv(file_path, userid):
    with open(file_path, 'r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            current_time = datetime.now(jakarta_tz)
            formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
            # row["_id"] = bson.objectid.ObjectId()
            row["created_date"] = formatted_time
            row["userid"] = userid

            checkpost = collection.find_one({"url": row["url"], "name_site": row["name_site"]})
            if checkpost is not None:
                print("Already exists in database")
            else:
                collection.insert_one(row)
                print("New record imported successfully!")

def main():
    parser = argparse.ArgumentParser(description="MongoDB Automation Script")
    parser.add_argument('--sites', help="Site name to process (optional)")
    parser.add_argument('--action', required=True, 
                        choices=['import_csv', 'update_posts', 'update_profiles'],
                        help="Action to perform")
    parser.add_argument('--userid', required=True, help="User ID")
    parser.add_argument('--file', help="CSV file path for import_csv action")

    args = parser.parse_args()

    if args.action == 'import_csv':
        if not args.file:
            print("Error: --file is required for import_csv action")
            sys.exit(1)
        import_csv(args.file, args.userid)
    elif args.action in ['update_posts', 'update_profiles']:
        process_continuously(args.action, args.userid, args.sites)

if __name__ == '__main__':
    main()