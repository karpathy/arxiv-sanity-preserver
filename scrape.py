# this script queries arxiv API to retrieve recent papers

import urllib
import time
import feedparser
import os

os.system('mkdir -p raw') # ?

# Base api query url
base_url = 'http://export.arxiv.org/api/query?';

# Search parameters
search_query = 'cat:cs.CV+OR+cat:cs.LG+OR+cat:cs.CL'
start = 0
total_results = 50000
results_per_iteration = 100
wait_time = 5

print 'Searching arXiv for %s' % search_query
for i in range(start,total_results,results_per_iteration):

  print "Results %i - %i" % (i,i+results_per_iteration)
  query = 'search_query=%s&sortBy=submittedDate&start=%i&max_results=%i' % (search_query,
                                                       i,
                                                      results_per_iteration)
  response = urllib.urlopen(base_url+query).read()
  fout = 'raw/out%d.xml' % (int(time.time()), )
  print('writing %s' % (fout, ))
  open(fout, 'w').write(response)

  # parse the response using feedparser
  feed = feedparser.parse(response)

  # Print out some information
  try:
    entry = feed.entries[0]
    print entry.title
    print entry.published
  except:
    pass

  print 'Sleeping for %i seconds' % wait_time 
  time.sleep(wait_time)
