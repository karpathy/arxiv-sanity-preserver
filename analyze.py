"""
Reads txt files of all papers and computes tfidf vectors for all papers.
Dumps results to file tfidf.p
"""
from sklearn.feature_extraction.text import TfidfVectorizer
import cPickle as pickle
import urllib2
import shutil
import time
import os
import random
import numpy as np

# read database
db = pickle.load(open('db.p', 'rb'))

# read all text files for all papers into memory
txts = []
pids = []
n=0
for pid,j in db.iteritems():
  n+=1
  idvv = '%sv%d' % (j['_rawid'], j['_version'])
  fname = os.path.join('txt', idvv) + '.pdf.txt'
  if os.path.isfile(fname): # some pdfs dont translate to txt
    txt = open(fname, 'r').read()
    if len(txt) < 100: # way too short and suspicious
      txts.append(txt) # todo later: maybe filter or something some of them
      pids.append(idvv)
      print 'read %d/%d (%s) with %d chars' % (n, len(db), idvv, len(txt))

# compute tfidf vectors with scikits
v = TfidfVectorizer(input='content', 
        encoding='utf-8', decode_error='replace', strip_accents='unicode', 
        lowercase=True, analyzer='word', stop_words='english', 
        token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',
        ngram_range=(1, 2), max_features = 10000, 
        norm='l2', use_idf=True, smooth_idf=True, sublinear_tf=False)

X = v.fit_transform(txts)
print v.vocabulary_
print X.shape

# write full matrix out
out = {}
out['X'] = X # this one is heavy!
print('writing tfidf.p')
pickle.dump(out, open("tfidf.p", "wb"))

# writing lighter metadata information into a separate (smaller) file
out = {}
out['vocab'] = v.vocabulary_
out['idf'] = v._tfidf.idf_
out['pids'] = pids # a full idvv string (id and version number)
out['ptoi'] = { x:i for i,x in enumerate(pids) } # pid to ix in X mapping
print('writing tfidf_meta.p')
pickle.dump(out, open("tfidf_meta.p", "wb"))

print 'precomputing nearest neighbor queries...'
X = X.todense() # originally it's a sparse matrix
sim_dict = {}
for i,pid in enumerate(pids):
  xquery = X[i, np.newaxis]
  ds = np.asarray(np.dot(X, xquery.T)).ravel() # L2 normalized tfidf vectors
  scores = [(ds[j], j) for j in xrange(X.shape[0])]
  scores.sort(reverse=True) # descending by distance  
  sim_dict[pids[i]] = [ pids[scores[j][1]] for j in xrange(50) ]
  if i%100==0: print '%d/%d...' % (i, len(pids))
print('writing sim_dict.p')
pickle.dump(sim_dict, open("sim_dict.p", "wb"))
