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
    txts.append(txt) # todo later: maybe filter or something some of them
    pids.append(idvv)
    print 'read %d/%d (%s) with %d chars' % (n, len(db), idvv, len(txt))

# compute tfidf vectors with scikits
v = TfidfVectorizer(input='content', 
        encoding='utf-8', decode_error='replace', strip_accents='unicode', 
        lowercase=True, analyzer='word', stop_words='english', 
        token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',
        ngram_range=(1, 2), max_features = 5000, 
        norm='l2', use_idf=True, smooth_idf=True, sublinear_tf=False)

X = v.fit_transform(txts)
print v.vocabulary_
print X.shape

out = {}
out['vocab'] = v.vocabulary_
out['idf'] = v._tfidf.idf_
out['X'] = X
out['pids'] = pids
out['ptoi'] = { x:i for i,x in enumerate(pids) } # pid to ix in X mapping

print('writing tfidf.p')
pickle.dump(out, open("tfidf.p", "wb"))

