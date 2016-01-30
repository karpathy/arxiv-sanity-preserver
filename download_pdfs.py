import cPickle as pickle
import urllib2
import shutil
import time
import os
import random

os.system('mkdir -p pdf') # ?

timeout_secs = 10 # after this many seconds we give up on a paper
numok = 0
numtot = 0
db = pickle.load(open('db.p', 'rb'))
have = os.listdir('pdf') # get list of all pdfs we already have
for pid,j in db.iteritems():
  
  pdfs = [x['href'] for x in j['links'] if x['type'] == 'application/pdf']
  assert len(pdfs) == 1
  pdf_url = pdfs[0] + '.pdf'
  basename = pdf_url.split('/')[-1]
  fname = os.path.join('pdf', basename)

  # try retrieve the pdf
  numtot += 1
  try:
    if not basename in have:
      print 'fetching %s into %s' % (pdf_url, fname)
      req = urllib2.urlopen(pdf_url, None, timeout_secs)
      with open(fname, 'wb') as fp:
          shutil.copyfileobj(req, fp)
      time.sleep(0.1 + random.uniform(0,0.2))
    else:
      print '%s exists, skipping' % (fname, )
    numok+=1
  except Exception, e:
    print 'error downloading: ', pdf_url
    print e
  
  print '%d/%d of %d downloaded ok.' % (numok, numtot, len(db))
  
print 'final number of papers downloaded okay: %d/%d' % (numok, len(db))
