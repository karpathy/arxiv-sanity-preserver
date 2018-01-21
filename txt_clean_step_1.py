"""
The script is intended to enrich an existing database pickle (by default db.p),
so this file will be loaded first, and then new results will be added to it.
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
  # main loop where we fetch the new results
  # print('database has %d entries at start' % (len(db), ))
  count = 0
  detail_line = []
  for key, details in db.items(): 
    # get title and arxiv id of paper 
    ai_title = details['title'].replace('\n', '').replace(',', ' ')
    
    pdfLink = details['links'][1]['href']
    temp = pdfLink.split("/")
    ai_id = temp[len(temp)-1]
    # get paper via ai_id.txt, find the title and abstract then divide the paper 
    if os.path.exists('./data/txt/'+ai_id+'.pdf.txt') and os.path.getsize('./data/txt/'+ai_id+'.pdf.txt') > 0:
      with open('./data/txt/'+ai_id+'.pdf.txt', 'r+') as file:
        print('opening '+ai_id)
        #store the title **
        f_title = open('./x_data/title/'+ai_id+'_title.txt','w+')
        f_title.write(ai_title)
        f_title.close()
        #store author's information
        w0 = '('+ai_title+')'
        w1 = '((?i)Abstract)'
        buff = file.read()
        #replace the return symbol to space 
        buff = buff.replace('\n',' ')
        try:
          pat = re.compile(w0+'(.*?)'+w1,re.S)
          result = pat.findall(buff)
          if len(result) > 0:
            f_auth = open('./x_data/author/'+ai_id+'_author.txt','w+')
            f_auth.write(''.join(str(v) for v in result))
            f_auth.close()
        except Exception as e:
          print('Excp.'+ai_title)
        #store the abstract **
        w2 = '((?i)Introduction)'     
        pat = re.compile(w1+'(.*?)'+w2,re.S)
        result = pat.findall(buff)
        if len(result) > 0:
          f_abs = open('./x_data/abstract/'+ai_id+'_abstract.txt','w+')
          f_abs.write(''.join(str(v) for v in result))
          f_abs.close()
        #store the paper body **
        w3 = '((?i)References)'     
        pat = re.compile(w2+'(.*?)'+w3,re.S)
        result = pat.findall(buff)
        if len(result) > 0:
          f_body = open('./x_data/body/'+ai_id+'_body.txt','w+')
          f_body.write(''.join(str(v) for v in result))
          f_body.close()
        #store paper references 
        pat = re.compile(w3+'(.*)',re.S)
        result = pat.findall(buff)
        if len(result) > 0:
          f_ref = open('./x_data/references/'+ai_id+'_references.txt','w+')
          f_ref.write(''.join(str(v) for v in result))
          f_ref.close()

          
      file.close()

 
        


