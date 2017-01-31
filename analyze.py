"""
Reads txt files of all papers and computes tfidf vectors for all papers.
Dumps results to file tfidf.p
"""
import os
import pickle

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

import utils

# read database
db_path = 'db.p'
db = pickle.load(open(db_path, 'rb'))

# read all text files for all papers into memory
txts, pids = [], []
n = 0
for pid,j in db.items():
  n += 1
  idvv = '%sv%d' % (j['_rawid'], j['_version'])
  txt_path = os.path.join('data', 'txt', idvv) + '.pdf.txt'
  if os.path.isfile(txt_path): # some pdfs dont translate to txt
    txt = open(txt_path, 'r').read()
    if len(txt) > 1000 and len(txt) < 500000: # 500K is VERY conservative upper bound
      txts.append(txt) # todo later: maybe filter or something some of them
      pids.append(idvv)
      print("read %d/%d (%s) with %d chars" % (n, len(db), idvv, len(txt)))
    else:
      print("skipped %d/%d (%s) with %d chars: suspicious!" % (n, len(db), idvv, len(txt)))
print("in total read in %d text files out of %d db entries." % (len(txts), len(db)))

# compute tfidf vectors with scikits
v = TfidfVectorizer(input='content', 
        encoding='utf-8', decode_error='replace', strip_accents='unicode', 
        lowercase=True, analyzer='word', stop_words='english', 
        token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',
        ngram_range=(1, 2), max_features = 10000, 
        norm='l2', use_idf=True, smooth_idf=True, sublinear_tf=True,
        max_df=1.0, min_df=1)

X = v.fit_transform(txts)
print(v.vocabulary_)
print(X.shape)

# write full matrix out
out = {}
out['X'] = X # this one is heavy!
tfidf_path = os.path.join('data', 'tfidf.p')
print("writing", tfidf_path)
utils.safe_pickle_dump(out, tfidf_path)

# writing lighter metadata information into a separate (smaller) file
out = {}
out['vocab'] = v.vocabulary_
out['idf'] = v._tfidf.idf_
out['pids'] = pids # a full idvv string (id and version number)
out['ptoi'] = { x:i for i,x in enumerate(pids) } # pid to ix in X mapping
meta_path = 'tfidf_meta.p'
print("writing", meta_path)
utils.safe_pickle_dump(out, meta_path)

print("precomputing nearest neighbor queries in batches...")
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

sim_path = 'sim_dict.p'
print("writing", sim_path)
utils.safe_pickle_dump(sim_dict, sim_path)
