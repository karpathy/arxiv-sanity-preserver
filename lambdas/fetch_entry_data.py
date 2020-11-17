import argparse
import os
import requests
import feedparser as fp
import boto3
import logging
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# leverage freezing
TABLE_NAME = os.environ['TABLE_NAME']
TABLE = None

# other globals
API_URL = 'http://export.arxiv.org/api/query'


DEFAULT_ARGS = {
    'search_query': 'cat:cs.CV+OR+cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE+OR+cat:stat.ML',
    'start_index': 0,
    'max_index': 10000,
    'res_per_iter': 100,
    'wait_time': 5.0,
    'break_on_no_add': 1
}

# args class to pull from the event
class FetchArgs:

    def __init__(self, data):
        self.data = data

    def getrange(self):
        return range(
            self.data['start_index'], 
            self.data['max_index'],
            self.data['res_per_iter']
        )
    
    @classmethod
    def argsFromEvent(cls, event):
        data = { **DEFAULT_ARGS, **event }
        return cls(data)



def encode_feedparser_dict(d):
    """ 
    Helper function to get rid of feedparser bs with a deep copy. 

    """
    if isinstance(d, fp.FeedParserDict) or isinstance(d, dict):
        j = {}
        for k in d.keys():
            j[k] = encode_feedparser_dict(d[k])
        return j
    elif isinstance(d, list):
        l = []
        for k in d:
            l.append(encode_feedparser_dict(k))
        return l
    else:
        return d


def parse_arxiv_url(url):
    """ 
    examples is http://arxiv.org/abs/1512.08756v2
    we want to extract the raw id (1512.08756) and the version (2)
    """
    ix = url.rfind('/')
    idversion = url[ix+1:] # extract just the id (and the version)
    parts = idversion.split('v')
    if len(parts) > 2:
        raise Exception("Error processing url: %s" % url)
    return parts[0], int(parts[1])


def parse_args(event):
    # parse input arguments
    return FetchArgs.argsFromEvent(event)


def fetch_entries(args):
    # generate entries from arxiv using argument parameters
    for index in args.getrange():
        params = {
            'search_query': args.data['search_query'],
            'start': index,
            'max_results': args.data['res_per_iter'],
            'sortBy': 'lastUpdatedDate'
        }
        logging.info("\nFetching %i entries starting from index %i..." % (params['max_results'], params['start']))
        response = requests.get(API_URL, params=params, timeout=5)
        if response.status_code != 200:
            raise Exception("Search returned with error code: %i" % response.status_code)
        else:
            yield fp.parse(response.content)

def extract_info(entries):
    # generate rawids, versions, and links
    for entry in entries:
        try: 
            rawid, version =  parse_arxiv_url(entry['id'])
            yield {
                'rawid': rawid, 
                'title': entry['title'],
                'version': version, 
                'links': entry['links'],
                'authors': entry['authors']
            }
        except Exception:
            raise

def main(event, context):
    # load table
    global TABLE
    if TABLE is None:
        TABLE = boto3.resource('dynamodb').Table(TABLE_NAME)   
    # logging
    logging.root.setLevel(logging.INFO) 

    # start fetching and parsing
    args = parse_args(event)
    logging.info("Searching arXiv for %s\nusing these options: %s" % (args.data['search_query'], args.data))
    
    try:
        for parsed_resp in fetch_entries(args):
            # check response
            if not hasattr(parsed_resp, 'entries'):
                raise Exception("No entries found in response.")
            # attempt an entry or replacement
            with TABLE.batch_writer() as batch:
                for entry_data in extract_info(parsed_resp.entries):
                    batch.put_item(Item=entry_data)
    except Exception as e:
        logging.error(e)


