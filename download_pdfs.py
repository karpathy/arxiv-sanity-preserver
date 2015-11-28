import cPickle as pickle
import urllib2
import shutil
import time
import os
import random

os.system('mkdir -p pdf') # ?

timeout_secs = 10
numok = 0
db = pickle.load(open('db.p', 'rb'))
for pid,j in db.iteritems():
  
  pdfs = [x['href'] for x in j['links'] if x['type'] == 'application/pdf']
  assert len(pdfs) == 1
  pdf_url = pdfs[0] + '.pdf'
  fname = os.path.join('pdf', pid) + '.pdf'

  # try retrieve the pdf
  try:
    print 'fetching %s into %s' % (pdf_url, fname)
    if not os.path.isfile(fname):
      req = urllib2.urlopen(pdf_url, None, timeout_secs)
      with open(fname, 'wb') as fp:
          shutil.copyfileobj(req, fp)
    else:
      print 'exists, skipping'
    numok+=1
    print '%d/%d downloaded ok.' % (numok, len(db))
    time.sleep(0.1 + random.uniform(0,0.2))

  except Exception, e:
    print 'error downloading: ', pdf_url
    print e

print 'num okay: %d/%d' % (numok, len(db))
