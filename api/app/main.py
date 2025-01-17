import subprocess as sp
import time
import re
import sys
import os
import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from pathlib import Path
from pydantic import BaseModel

from threading import Thread
from app.model.mongodb import MongoDB

client = MongoDB(host=os.environ['MONGO_HOST'], port=int(os.environ['MONGO_PORT']), username=os.environ['MONGO_USER'], password=os.environ['MONGO_PASS'])

app = FastAPI(title='API docs for darkweb')
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])

count_by_source = [
    {
        '$group': {
            '_id': {
                'source': '$website', 
            }, 
            'alias': {"$addToSet":'$website_alias'},
            'count': {
                '$sum': 1
            }
        }
    }, {
        '$project': {
            '_id': 0, 
            'source': '$_id.source',
            'alias': '$alias', 
            'category': '$category',
            'count': '$count'
        }
    }
]

count_by_category = [
    {
        '$match': {
            'category': {'$ne':None},
        }
    }, {
        '$group': {
            '_id': {
                'category': '$category'
            }, 
            'category': {"$addToSet":'$category'},
            'count': {
                '$sum': 1
            }
        }
    }, {
        '$project': {
            '_id':0,
            'category': '$_id.category',
            'count': '$count'
        }
    }
]

count_by_date = [
    {
        '$group': {
            '_id': {
                'created_date': '$created_date'
            }, 
            'category': {"$addToSet":'$category'},
            'count': {
                '$sum': 1
            }
        }
    }, {
        '$project': {
            '_id':0,
            'created_at': '$_id.created_date', 
            'category': '$category', 
            'count': '$count'
        }
    }
]

count_by_emotion = [
    {
        '$group': {
            '_id': {
                'emotion': '$analytics.emotion'
            }, 
            'category': {"$addToSet":'$category'},
            'count': {
                '$sum': 1
            }
        }
    }, {
        '$project': {
            '_id':0,
            'emotion': '$_id.emotion',
            'category': '$category', 
            'count': '$count'
        }
    }
]

count_by_sentiment = [
    {
        '$group': {
            '_id': {
                'sentiment': '$analytics.sentiment'
            }, 
            'category': {"$addToSet":'$category'},
            'count': {
                '$sum': 1
            }
        }
    }, {
        '$project': {
            '_id':0,
            'sentiment': '$_id.sentiment',
            'category': '$category', 
            'count': '$count'
        }
    }
]

count_by_issues = [
    {
        '$group': {
            '_id': {
                'issues': '$issue'
            }, 
            'category': {"$addToSet":'$category'},
            'count': {
                '$sum': 1
            }
        }
    }, {
        '$project': {
            '_id':0,
            'issues': '$_id.issues',
            'category': '$category', 
            'count': '$count'
        }
    }, {
        '$sort': {
            'count': -1
        }
    }
]

exposure = [
    {
        '$project': {
            'date': {
                '$dateToString': {
                    'format': '%Y-%m-%d', 
                    'date': '$created_at'
                }
            }
        }
    }, {
        '$group': {
            '_id': '$date', 
            'total': {
                '$sum': 1
            }
        }
    }, {
        '$project': {
            '_id': 0, 
            'date': '$_id', 
            'total': '$total'
        }
    }, {
        '$sort': {
            'date': 1
        }
    }
]

@app.get("/api/v1/darkweb-api/get-exposures")
def get_exposure(since: str, until: str, category: str="forum", query: str=None):
    client.create_db("crawler")
    client.create_collection("darkweb")

    match_agg = [
        {
            '$match': {
                'created_at': {
                    '$gte': datetime.datetime.strptime(since, '%Y-%m-%d'),
                    '$lte': datetime.datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                }
            }
        }
    ]

    if query != None:
        match_agg[0]['$match']['content'] = re.compile(query, re.IGNORECASE)

    if category != None:
        match_agg[0]['$match']['category'] = category

    docs = client.aggregate(match_agg + exposure)

    docs = list(docs)

    if len(docs) == 0:
        return {
            'success': True,
            'message': 'Successfully retrieved exposure.',
            'data': []
        }

    return {
        'success': True,
        'message': 'Successfully retrieved exposure.',
        'data': docs
    }

@app.get("/api/v1/darkweb-api/get-posts")
def get_posts(since: str, until: str, page_size: int, page_num: int, query: str=None, category: str=None, emotion: str=None, sentiment: str=None, source: str=None, issue: str=None, accounts: str=None):
    client.create_db("crawler")
    client.create_collection("darkweb")

    if page_size < 1 or page_num < 1:
        raise HTTPException(400, detail="page_size and page_num should be greater than 0")

    skips = page_size * (page_num - 1)

    posts_agg = [
        {
            '$match': {
                'created_at': {
                    '$gte': datetime.datetime.strptime(since, '%Y-%m-%d'),
                    '$lte': datetime.datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                }
            }
        }, {
            '$addFields': {
                'post_url': {"$concat":['$website','$post_id']}
            }
        }, {
            '$sort': {
                'date': -1
            }
        }, {
            '$project': {
                '_id': 0
            }
        }, {
            '$skip': skips
        }, {
            '$limit': page_size
        }
    ]

    website_alias = [
    'bbcnews',
    'nytimes',
    'dark_fox',
    'endchan',
    'picochan',
    'breaking_bad',
    'abyss'
    ]

    if query != None:
        posts_agg[0]['$match']['content'] = re.compile(query, re.IGNORECASE)

    if category != None:
        print(category)
        posts_agg[0]['$match']['category'] = category

    if emotion != None:
        posts_agg[0]['$match']['analytics.emotion'] = emotion

    if sentiment != None:
        posts_agg[0]['$match']['analytics.sentiment'] = sentiment

    if issue != None:
        posts_agg[0]['$match']['issue.keyword'] = issue

    if source != None:
        if source in website_alias:
            posts_agg[0]['$match']['website_alias'] = source
        else:
            posts_agg[0]['$match']['website'] = source

    if accounts != None:
        posts_agg[0]['$match']['poster'] = accounts

    docs = client.aggregate(posts_agg)

    docs = list(docs)

    if len(docs) == 0:
        return {
            'success': True,
            'message': 'Successfully retrieved posts.',
            'data': []
        }

    return {
        'success': True,
        'message': 'Successfully retrieved posts.',
        'data': docs
    }

@app.get("/api/v1/darkweb-api/get-top-accounts")
def get_top_accounts(since: str, until: str, category: str=None, query: str=None, top_n: int=10):
    client.create_db("crawler")
    client.create_collection("darkweb")

    match_agg = [
        {
            '$match': {
                'created_at': {
                    '$gte': datetime.datetime.strptime(since, '%Y-%m-%d'),
                    '$lte': datetime.datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                }
            }
        }, {
            '$addFields': {
                'accounts': '$username', 
                'accounts': '$poster'
            }
        }, {
            '$group': {
                '_id': '$accounts', 
                'posts': {
                    '$sum': 1
                }
            }
        }, {
            '$sort': {
                'posts': -1
            }
        }, {
            '$limit': top_n
        }
    ]

    if category != None:
        print(category)
        match_agg[0]['$match']['category'] = category

    if query != None:
        match_agg[0]['$match']['content'] = re.compile(query, re.IGNORECASE)

    docs = client.aggregate(match_agg)

    docs = list(docs)

    docs_ = []

    for doc in docs:
        try:
            doc['_id'] = doc['_id'].strip()
            docs_.append(doc)
        except:
            pass

    if len(docs_) == 0:
        return {
            'success': True,
            'message': 'Successfully retrieved posts.',
            'data': []
        }
    
    return {
        'success': True,
        'message': 'Successfully retrieved posts.',
        'data': docs_
    }

@app.get("/api/v1/darkweb-api/get-content-by-source")
def get_content_by_source(since: str, until: str, category: str=None, query: str=None):
    client.create_db("crawler")
    client.create_collection("darkweb")

    source_agg = count_by_source

    match_agg = [
        {
            '$match': {
                'created_at':{
                    "$gte": datetime.datetime.strptime(since, '%Y-%m-%d'),
                    "$lte": datetime.datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59),
                }
            }
        }
    ]

    docs_agg = match_agg + source_agg

    if query != None:
        match_agg[0]['$match']['content'] = re.compile(query, re.IGNORECASE)

    if category != None:
        match_agg[0]['$match']['category'] = category
        docs_agg += [
            {
                '$project': {
                    '_id': 0, 
                    'source': '$source', 
                    'count': '$count',
                    'alias':'$alias'
                }
            }
        ]

    docs = client.aggregate(docs_agg)

    docs = list(docs)

    if len(docs) == 0:
        return {
            'success': True,
            'message': 'Successfully retrieved content by source.',
            'data': []
        }

    return {
        'success': True,
        'message': 'Successfully retrieved content by source.',
        'data': docs
    }

@app.get("/api/v1/darkweb-api/get-content-by-category")
def get_content_by_category(since: str, until: str, category: str=None, query: str=None):
    client.create_db("crawler")
    client.create_collection("darkweb")

    category_agg = count_by_category

    match_agg = [
        {
            '$match': {
                'created_at':{
                    "$gte": datetime.datetime.strptime(since, '%Y-%m-%d'),
                    "$lte": datetime.datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59),
                }
            }
        }
    ]

    docs_agg = match_agg + category_agg

    if query != None:
        match_agg[0]['$match']['content'] = re.compile(query, re.IGNORECASE)

    if category != None:
        match_agg[0]['$match']['category'] = category
        docs_agg += [
            {
                '$project': {
                    '_id': 0, 
                    'category': '$category', 
                    'count': '$count'
                }
            }
        ]

    docs = client.aggregate(docs_agg)

    docs = list(docs)

    if len(docs) == 0:
        return {
            'success': True,
            'message': 'Successfully retrieved content by category.',
            'data': []
        }

    return {
        'success': True,
        'message': 'Successfully retrieved content by category.',
        'data': docs
    }

@app.get("/api/v1/darkweb-api/get-content-by-date")
def get_content_by_date(since: str, until: str, category: str=None, query: str=None):
    client.create_db("crawler")
    client.create_collection("darkweb")

    date_agg = count_by_date
    
    match_agg = [
        {
            '$match': {
                'created_at':{
                    "$gte": datetime.datetime.strptime(since, '%Y-%m-%d'),
                    "$lte": datetime.datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59),
                }
            }
        }
    ]

    all_docs = client.aggregate(match_agg)

    pub_date = []
    for doc in all_docs:
        if 'created_date' in doc:
            pub_date.append(doc['created_date'])
        elif 'created_at' in doc:
            # date_obj = datetime.datetime.fromisoformat(doc['published_at'])
            date_string = doc['created_at'].strftime('%Y-%m-%d')
            pub_date.append(date_string)

    pub_date = list(set(pub_date))

    print(f"pub_date: {len(pub_date)}")

    docs_agg = match_agg + date_agg + [{'$sort':{"created_at":1}}]

    if query != None:
        match_agg[0]['$match']['content'] = {"$regex":query}

    if category != None:
        match_agg[0]['$match']['category'] = category
        docs_agg += [
            {
                '$project': {
                    '_id': 0, 
                    'created_at': '$created_at', 
                    'count': '$count'
                }
            }
        ]

    # print(docs_agg)

    docs = client.aggregate(docs_agg)

    docs = list(docs)

    doc_date = []

    for doc in docs:
        doc_date.append(doc['created_at'])

    print(f"docs: {len(doc_date)}")

    # pub_date_sorted = [datetime.datetime.strptime(date, "%Y-%m-%d") for date in pub_date]

    for date in pub_date:
        if date not in doc_date:
            docs.append(
                {
                    "created_at": date,
                    "category": [],
                    "count":0
                }
            )

    sorted_docs = sorted(docs[1:], key=lambda d: datetime.datetime.strptime(d['created_at'], "%Y-%m-%d"))

    sorted_docs = [docs[0]] + sorted_docs

    for doc in sorted_docs:
        doc['published_at'] = doc['created_at']

    if len(sorted_docs) == 0:
        return {
            'success': True,
            'message': 'Successfully retrieved content by date.',
            'data': []
        }

    return {
        'success': True,
        'message': 'Successfully retrieved content by source.',
        'data': sorted_docs
    }

@app.get("/api/v1/darkweb-api/get-content-by-emotion")
def get_content_by_emotion(since: str, until: str, category: str=None, query: str=None):
    client.create_db("crawler")
    client.create_collection("darkweb")

    emotion_agg = count_by_emotion

    match_agg = [
        {
            '$match': {
                'created_at':{
                    "$gte": datetime.datetime.strptime(since, '%Y-%m-%d'),
                    "$lte": datetime.datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59),
                }
            }
        }
    ]

    docs_agg = match_agg + emotion_agg

    if query != None:
        match_agg[0]['$match']['content'] = re.compile(query, re.IGNORECASE)

    if category != None:
        match_agg[0]['$match']['category'] = category
        docs_agg += [
            {
                '$project': {
                    '_id': 0, 
                    'emotion': '$emotion', 
                    'count': '$count'
                }
            }
        ]

    docs = client.aggregate(docs_agg)

    docs = list(docs)

    if len(docs) == 0:
        return {
            'success': True,
            'message': 'Successfully retrieved content by date.',
            'data': []
        }

    return {
        'success': True,
        'message': 'Successfully retrieved content by source.',
        'data': docs
    }

@app.get("/api/v1/darkweb-api/get-content-by-sentiment")
def get_content_by_sentiment(since: str, until: str, category: str=None, query: str=None):
    client.create_db("crawler")
    client.create_collection("darkweb")

    sentiment_agg = count_by_sentiment

    match_agg = [
        {
            '$match': {
                'created_at':{
                    "$gte": datetime.datetime.strptime(since, '%Y-%m-%d'),
                    "$lte": datetime.datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59),
                }
            }
        }
    ]

    docs_agg = match_agg + sentiment_agg

    if query != None:
        match_agg[0]['$match']['content'] = re.compile(query, re.IGNORECASE)

    if category != None:
        match_agg[0]['$match']['category'] = category
        docs_agg += [
            {
                '$project': {
                    '_id': 0, 
                    'sentiment': '$sentiment', 
                    'count': '$count'
                }
            }
        ]

    docs = client.aggregate(docs_agg)

    docs = list(docs)

    if len(docs) == 0:
        return {
            'success': True,
            'message': 'Successfully retrieved content by date.',
            'data': []
        }

    return {
        'success': True,
        'message': 'Successfully retrieved content by source.',
        'data': docs
    }

@app.get("/api/v1/darkweb-api/get-content-by-issues")
def get_content_by_issues(since: str, until: str, category: str=None, query: str=None):
    client.create_db("crawler")
    client.create_collection("darkweb")

    issues_agg = count_by_issues

    match_agg = [
        {
            '$match': {
                'created_at':{
                    "$gte": datetime.datetime.strptime(since, '%Y-%m-%d'),
                    "$lte": datetime.datetime.strptime(until, '%Y-%m-%d').replace(hour=23, minute=59, second=59),
                },
                'issue.keyword': {'$ne':None}
            }
        }
    ]

    docs_agg = match_agg + issues_agg

    if query != None:
        match_agg[0]['$match']['content'] = re.compile(query, re.IGNORECASE)

    if category != None:
        match_agg[0]['$match']['category'] = category
        docs_agg += [{
            '$project': {
                '_id': 0, 
                'issues': '$issues', 
                'count': '$count'
            }
        }]

    docs = client.aggregate(docs_agg)

    docs = list(docs)

    if len(docs) == 0:
        return {
            'success': True,
            'message': 'Successfully retrieved content by date.',
            'data': []
        }

    return {
        'success': True,
        'message': 'Successfully retrieved content by source.',
        'data': docs
    }

# @app.get("/api/v1/darkweb-api/python-check")
def python_check():
    return {
        'success': True,
        'message': 'Successfully retrieved top retweets by day.',
        'data': sp.check_output(['python', '--version'])
    }
