from __future__ import print_function

try:
  from urllib.parse import urlparse, urlencode
  from urllib.request import urlopen, Request
  from urllib.error import HTTPError
except ImportError:
  from urlparse import urlparse
  from urllib import urlencode
  from urllib2 import urlopen, Request, HTTPError

try:
  import pickle as pickle
except:
  import cPickle as pickle

import shutil
import time
import os
import random

def download_pdf(paper_timeout=10,#after this many seconds we give up on a paper
                 database_file='db.p',#database file
                 out_dir='pdf'):
  os.system('mkdir -p pdf') # ?
  timeout_secs = paper_timeout # after this many seconds we give up on a paper
  numok = 0
  numtot = 0
  db = pickle.load(open(database_file, 'rb'))
  have = set(os.listdir(out_dir)) # get list of all pdfs we already have
  for pid,j in db.items():
    pdfs = [x['href'] for x in j['links'] if x['type'] == 'application/pdf']
    assert len(pdfs) == 1
    pdf_url = pdfs[0] + '.pdf'
    basename = pdf_url.split('/')[-1]
    fname = os.path.join(out_dir, basename)

    # try retrieve the pdf
    numtot += 1
    try:
      if not basename in have:
        print('fetching %s into %s' % (pdf_url, fname))
        req = urlopen(pdf_url, None, timeout_secs)
        with open(fname, 'wb') as fp:
            shutil.copyfileobj(req, fp)
        time.sleep(0.1 + random.uniform(0,0.2))
      else:
        print('%s exists, skipping' % (fname, ))
      numok += 1
    except Exception as e:
      print('error downloading: ', pdf_url)
      print(e)
    print('%d/%d of %d downloaded ok.' % (numok, numtot, len(db)))
  print('final number of papers downloaded okay: %d/%d' % (numok, len(db)))
  return numok, db

def main():
  print("Starting to download PDFs")
  download_pdf()

if __name__ == '__main__':
  main()
