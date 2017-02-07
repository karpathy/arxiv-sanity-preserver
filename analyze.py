"""
Reads txt files of all papers and computes tfidf vectors for all papers.
Dumps results to file tfidf.p
"""
import os
import pickle
from random import shuffle, seed

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from utils import Config, safe_pickle_dump

seed(1337)
max_train = 10000 # max number of tfidf training documents (chosen randomly), for memory efficiency

# read database
db = pickle.load(open(Config.db_path, 'rb'))

# read all text files for all papers into memory
txt_paths, pids = [], []
n = 0
for pid,j in db.items():
  n += 1
  idvv = '%sv%d' % (j['_rawid'], j['_version'])
  txt_path = os.path.join('data', 'txt', idvv) + '.pdf.txt'
  if os.path.isfile(txt_path): # some pdfs dont translate to txt
    with open(txt_path, 'r') as f:
      txt = f.read()
    if len(txt) > 1000 and len(txt) < 500000: # 500K is VERY conservative upper bound
      txt_paths.append(txt_path) # todo later: maybe filter or something some of them
      pids.append(idvv)
      print("read %d/%d (%s) with %d chars" % (n, len(db), idvv, len(txt)))
    else:
      print("skipped %d/%d (%s) with %d chars: suspicious!" % (n, len(db), idvv, len(txt)))
  else:
    print("could not find %s in txt folder." % (txt_path, ))
print("in total read in %d text files out of %d db entries." % (len(txt_paths), len(db)))

# compute tfidf vectors with scikits
v = TfidfVectorizer(input='content', 
        encoding='utf-8', decode_error='replace', strip_accents='unicode', 
        lowercase=True, analyzer='word', stop_words='english', 
        token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',
        ngram_range=(1, 2), max_features = 10000, 
        norm='l2', use_idf=True, smooth_idf=True, sublinear_tf=True,
        max_df=1.0, min_df=1)

# create an iterator object to conserve memory
def make_corpus(paths):
  for p in paths:
    with open(p, 'r') as f:
      txt = f.read()
    yield txt

# train
train_txt_paths = list(txt_paths) # duplicate
shuffle(train_txt_paths) # shuffle
train_txt_paths = train_txt_paths[:min(len(train_txt_paths), max_train)] # crop
print("training on %d documents..." % (len(train_txt_paths), ))
train_corpus = make_corpus(train_txt_paths)
v.fit(train_corpus)

# transform
print("transforming %d documents..." % (len(txt_paths), ))
corpus = make_corpus(txt_paths)
X = v.transform(corpus)
print(v.vocabulary_)
print(X.shape)

# write full matrix out
out = {}
out['X'] = X # this one is heavy!
print("writing", Config.tfidf_path)
safe_pickle_dump(out, Config.tfidf_path)

# writing lighter metadata information into a separate (smaller) file
out = {}
out['vocab'] = v.vocabulary_
out['idf'] = v._tfidf.idf_
out['pids'] = pids # a full idvv string (id and version number)
out['ptoi'] = { x:i for i,x in enumerate(pids) } # pid to ix in X mapping
print("writing", Config.meta_path)
safe_pickle_dump(out, Config.meta_path)

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

print("writing", Config.sim_path)
safe_pickle_dump(sim_dict, Config.sim_path)
