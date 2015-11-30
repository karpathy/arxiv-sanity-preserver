from sklearn.feature_extraction.text import TfidfVectorizer
import cPickle as pickle
import urllib2
import shutil
import time
import os
import random

db = pickle.load(open('db.p', 'rb'))
txts = []
pids = []
n=0
for pid,j in db.iteritems():
  n+=1
  fname = os.path.join('txt', pid) + '.pdf.txt'
  if os.path.isfile(fname):
    txt = open(fname, 'r').read()
    txts.append(txt) # todo later: maybe filter or something some of them
    pids.append(pid)
  print 'reading %d/%d' % (n, len(db))

v = TfidfVectorizer(input='content', 
        encoding='utf-8', decode_error='replace', strip_accents='unicode', lowercase=True, 
        analyzer='word', stop_words='english', 
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
out['ptoi'] = { x:i for i,x in enumerate(pids) } # pid to ix mapping

print('writing tfidf.p')
pickle.dump(out, open("tfidf.p", "wb"))

