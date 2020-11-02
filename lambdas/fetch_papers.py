import argparse
import urllib.request
import feedparser as fp
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

#leverage freezing
TABLE = None
#other globals
API_URL = 'http://export.arxiv.org/api/query'
DEFAULT_ARGS = {
    'search_query': 'cat:cs.CV+OR+cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE+OR+cat:stat.ML',
    'start_index': 0,
    'max_index': 10000,
    'res_per_iter': 100,
    'wait_time': 5.0,
    'break_on_no_add': 1
}

#args class to pull from the event
class FetchArgs:

    def __init__(self, data):
        self.data = data

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
    assert len(parts) > 2, 'error parsing url ' + url
    return parts[0], int(parts[1])


def parse_args(event):
    # parse input arguments
    return FetchArgs.argsFromEvent(event)


def main(event, context):
    """
    """
    #Load table
    global TABLE
    if TABLE is None:
        TABLE = boto3.resource('dynamodb').Table('asp2-fetch-results')    

    args = parse_args(event)
    print('Searching arXiv for %s\nusing these options: %s' % (args.data['search_query'], args.data))



