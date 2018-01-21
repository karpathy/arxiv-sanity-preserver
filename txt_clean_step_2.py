"""
This script is intended to move 100 samples of cleaned data into test directry
in further use, this script can be modified as a filter for remove incompleted data 
"""

import mmap
import re
import os
import time
import pickle
import random
import argparse
import urllib.request
import feedparser
from shutil import copyfile

from utils import Config, safe_pickle_dump

def encode_feedparser_dict(d):
  """ 
  helper function to get rid of feedparser bs with a deep copy. 
  I hate when libs wrap simple things in their own classes.
  """
  if isinstance(d, feedparser.FeedParserDict) or isinstance(d, dict):
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
  we want to extract the raw id and the version
  """
  ix = url.rfind('/')
  idversion = url[ix+1:] # extract just the id (and the version)
  parts = idversion.split('v')
  assert len(parts) == 2, 'error parsing url ' + url
  return parts[0], int(parts[1])

if __name__ == "__main__":

  # parse input arguments
  parser = argparse.ArgumentParser()
  parser.add_argument('--search-query', type=str,
                      default='cat:cs.CV+OR+cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE+OR+cat:stat.ML',
                      help='query used for arxiv API. See http://arxiv.org/help/api/user-manual#detailed_examples')
  parser.add_argument('--start-index', type=int, default=0, help='0 = most recent API result')
  parser.add_argument('--max-index', type=int, default=30000, help='upper bound on paper index we will fetch')
  parser.add_argument('--results-per-iteration', type=int, default=100, help='passed to arxiv API')
  parser.add_argument('--wait-time', type=float, default=5.0, help='lets be gentle to arxiv API (in number of seconds)')
  parser.add_argument('--break-on-no-added', type=int, default=1, help='break out early if all returned query papers are already in db? 1=yes, 0=no')
  args = parser.parse_args()

  # misc hardcoded variables
  base_url = 'http://export.arxiv.org/api/query?' # base api query url
  # print('Searching arXiv for %s' % (args.search_query, ))

  # lets load the existing database to memory
  try:
    db = pickle.load(open(Config.db_path, 'rb'))
  except Exception as e:
    print('error loading existing database:')
    print(e)
    print('starting from an empty database')
    db = {}

  # -----------------------------------------------------------------------------
  # copy 100 samples into sample dir
  count = 0;
  detail_line = [];
  for key, details in db.items(): 
 
    #if count > 99:
      #break
    
    # get title and arxiv id of paper 
    ai_title = details['title'].replace('\n', '').replace(',', ' ')
    
    pdfLink = details['links'][1]['href']
    temp = pdfLink.split("/")
    ai_id = temp[len(temp)-1]
    # check every part of a paper is exist then copy all 
    if os.path.exists('./data/txt/'+ai_id+'.pdf.txt') and os.path.getsize('./data/txt/'+ai_id+'.pdf.txt') > 0:
      if os.path.exists('./x_data/title/'+ai_id+'_title.txt') and os.path.getsize('./x_data/title/'+ai_id+'_title.txt') > 0:
        if os.path.exists('./x_data/author/'+ai_id+'_author.txt') and os.path.getsize('./x_data/author/'+ai_id+'_author.txt') > 0:
          if os.path.exists('./x_data/abstract/'+ai_id+'_abstract.txt') and os.path.getsize('./x_data/abstract/'+ai_id+'_abstract.txt') > 0:
            if os.path.exists('./x_data/body/'+ai_id+'_body.txt') and os.path.getsize('./x_data/body/'+ai_id+'_body.txt') > 0:
              if os.path.exists('./x_data/references/'+ai_id+'_references.txt') and os.path.getsize('./x_data/references/'+ai_id+'_references.txt') > 0:
                count += 1
                src = "./x_data/"
                dst = "./x_data/sample/"
                copyfile(src+'title/'+ai_id+'_title.txt', dst+'title/'+ai_id+'_title.txt')
                copyfile(src+'author/'+ai_id+'_author.txt', dst+'author/'+ai_id+'_author.txt')
                copyfile(src+'abstract/'+ai_id+'_abstract.txt', dst+'abstract/'+ai_id+'_abstract.txt')
                copyfile(src+'body/'+ai_id+'_body.txt', dst+'body/'+ai_id+'_body.txt')
                copyfile(src+'references/'+ai_id+'_references.txt', dst+'references/'+ai_id+'_references.txt')


 
        


