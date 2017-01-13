"""
Reads txt files of all papers and computes tfidf vectors for all papers.
Dumps results to file tfidf.p
"""
from __future__ import print_function

from sklearn.feature_extraction.text import TfidfVectorizer
try:
  import pickle as pickle
except:
  import cPickle as pickle

import shutil
import time
import os
import random
import numpy as np

import utils

# read database
db = pickle.load(open('db.p', 'rb'))

# read all text files for all papers into memory
txts = []
pids = []
n=0
for pid,j in db.items():
  n+=1
  idvv = '%sv%d' % (j['_rawid'], j['_version'])
  fname = os.path.join('txt', idvv) + '.pdf.txt'
  if os.path.isfile(fname): # some pdfs dont translate to txt
    txt = open(fname, 'r').read()
    if len(txt) > 100: # way too short and suspicious
      txts.append(txt) # todo later: maybe filter or something some of them
      pids.append(idvv)
      print('read %d/%d (%s) with %d chars' % (n, len(db), idvv, len(txt)))
    else:
      print('skipped %d/%d (%s) with %d chars: suspicious!' % (n, len(db), idvv, len(txt)))

# compute tfidf vectors with scikits
v = TfidfVectorizer(input='content', 
        encoding='utf-8', decode_error='replace', strip_accents='unicode', 
        lowercase=True, analyzer='word', stop_words='english', 
        token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',
        ngram_range=(1, 2), max_features = 20000, 
        norm='l2', use_idf=True, smooth_idf=True, sublinear_tf=False)

X = v.fit_transform(txts)
print(v.vocabulary_)
print(X.shape)

# write full matrix out
out = {}
out['X'] = X # this one is heavy!
print('writing tfidf.p')
utils.safe_pickle_dump(out, "tfidf.p")

# writing lighter metadata information into a separate (smaller) file
out = {}
out['vocab'] = v.vocabulary_
out['idf'] = v._tfidf.idf_
out['pids'] = pids # a full idvv string (id and version number)
out['ptoi'] = { x:i for i,x in enumerate(pids) } # pid to ix in X mapping
print('writing tfidf_meta.p')
utils.safe_pickle_dump(out, "tfidf_meta.p")

print('precomputing nearest neighbor queries in batches...')
X = X.todense() # originally it's a sparse matrix
sim_dict = {}
batch_size = 200
for i in range(0,len(pids),batch_size):
  i1 = min(len(pids), i+batch_size)
  xquery = X[i:i1] # BxD
  ds = -np.asarray(np.dot(X, xquery.T)) #NxD * DxB => NxB
  IX = np.argsort(ds, axis=0) # NxB
  for j in range(i1-i):
    sim_dict[pids[i+j]] = [pids[q] for q in list(IX[:50,j])]
  print('%d/%d...' % (i, len(pids)))

print('writing sim_dict.p')
utils.safe_pickle_dump(sim_dict, "sim_dict.p")
