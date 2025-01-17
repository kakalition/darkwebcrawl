import re
import datetime


def clean_html(html_content):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', html_content)
    return cleantext


def if_exists(post_id, mongo_client):
    mongo_conn = mongo_client
    collection = mongo_conn.database['jobs_crawler']
    return collection.count_documents({"post_id": post_id})


def if_exists_profile(username, website, mongo_client):
    mongo_conn = mongo_client
    collection = mongo_conn.database['jobs_crawler']
    return collection.count_documents({"username": username, "website": website})


def fill_date(data, post_id, mongo_conn):
    now = datetime.datetime.now()
    collection = mongo_conn.database['darkweb']
    
    # Check if record exists
    existing_record = collection.find_one({"post_id": post_id})
    
    if existing_record is None:
        # New record - set both timestamps
        data['created_at'] = now
        data['created_date'] = now.strftime("%Y-%m-%d")
    else:
        # Existing record - keep original created_at and created_date
        data['created_at'] = existing_record['created_at']
        data['created_date'] = existing_record['created_date']
    
    # Always update the updated_at timestamp
        data['updated_at'] = now
    
    return data


def fill_date_profile(data, username, website, mongo_conn):
    now = datetime.datetime.now()
    collection = mongo_conn.database['darkweb_profiles']
    
    # Check if profile exists
    existing_profile = collection.find_one({"username": username, "website": website})
    
    if existing_profile is None:
        # New profile - set both timestamps
        data['created_at'] = now
        data['created_date'] = now.strftime("%Y-%m-%d")
    else:
        # Existing profile - keep original created_at and created_date
        data['created_at'] = existing_profile['created_at']
        data['created_date'] = existing_profile['created_date']
    
    # Always update the updated_at timestamp
        data['updated_at'] = now
    
    return data