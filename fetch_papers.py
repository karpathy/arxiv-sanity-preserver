"""
Queries arxiv API and downloads papers (the query is a parameter).
The script is intended to enrich an existing database pickle (by default db.p),
so this file will be loaded first, and then new results will be added to it.
"""

import urllib
import time
import feedparser
import os
import cPickle as pickle
import argparse
import random
import utils

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
  idversion = j['id'][ix+1:] # extract just the id (and the version)
  parts = idversion.split('v')
  assert len(parts) == 2, 'error parsing url ' + url
  return parts[0], int(parts[1])

if __name__ == "__main__":

  # parse input arguments
  parser = argparse.ArgumentParser()
  parser.add_argument('--db_path', dest='db_path', type=str, default='db.p', help='database pickle filename that we enrich')
  parser.add_argument('--search_query', dest='search_query', type=str,
                      default='cat:cs.CV+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.NE+OR+cat:stat.ML',
                      help='query used for arxiv API. See http://arxiv.org/help/api/user-manual#detailed_examples')
  parser.add_argument('--start_index', dest='start_index', type=int, default=0, help='0 = most recent API result')
  parser.add_argument('--max_index', dest='max_index', type=int, default=10000, help='upper bound on paper index we will fetch')
  parser.add_argument('--results_per_iteration', dest='results_per_iteration', type=int, default=100, help='passed to arxiv API')
  parser.add_argument('--wait_time', dest='wait_time', type=float, default=5.0, help='lets be gentle to arxiv API (in number of seconds)')
  parser.add_argument('--break_on_no_added', dest='break_on_no_added', type=int, default=1, help='break out early if all returned query papers are already in db? 1=yes, 0=no')
  args = parser.parse_args()

  # misc hardcoded variables
  base_url = 'http://export.arxiv.org/api/query?' # base api query url
  print 'Searching arXiv for %s' % (args.search_query, )

  # lets load the existing database to memory
  try:
    db = pickle.load(open(args.db_path, 'rb'))
  except Exception, e:
    print 'error loading existing database:'
    print e
    print 'starting from an empty database'
    db = {}

  # -----------------------------------------------------------------------------
  # main loop where we fetch the new results
  print 'database has %d entries at start' % (len(db), )
  num_added_total = 0
  for i in range(args.start_index, args.max_index, args.results_per_iteration):

    print "Results %i - %i" % (i,i+args.results_per_iteration)
    query = 'search_query=%s&sortBy=lastUpdatedDate&start=%i&max_results=%i' % (args.search_query,
                                                         i, args.results_per_iteration)
    response = urllib.urlopen(base_url+query).read()
    parse = feedparser.parse(response)
    num_added = 0
    num_skipped = 0
    for e in parse.entries:

      j = encode_feedparser_dict(e)

      # extract just the raw arxiv id and version for this paper
      rawid, version = parse_arxiv_url(j['id'])
      j['_rawid'] = rawid
      j['_version'] = version

      # add to our database if we didn't have it before, or if this is a new version
      if not rawid in db or j['_version'] > db[rawid]['_version']:
        db[rawid] = j
        print 'updated %s added %s' % (j['updated'], j['title'])
        num_added += 1
      else:
        num_skipped += 1

    # print some information
    print 'Added %d papers, already had %d.' % (num_added, num_skipped)

    if len(parse.entries) == 0:
      print 'Received no results from arxiv. Rate limiting? Exitting. Restart later maybe.'
      print response
      break

    if num_added == 0 and args.break_on_no_added == 1:
      print 'No new papers were added. Assuming no new papers exist. Exitting.'
      break

    print 'Sleeping for %i seconds' % (args.wait_time , )
    time.sleep(args.wait_time + random.uniform(0, 3))

  # save the database before we quit
  print 'saving database with %d papers to %s' % (len(db), args.db_path)
  utils.safe_pickle_dump(db, args.db_path)
