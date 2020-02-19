# -*- coding: utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
"""
Reads txt files of all papers and computes tfidf vectors for all papers.
Dumps results to file tfidf.p
"""
import os
import pickle
from random import shuffle, seed

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from utils import Config, safe_pickle_dump, dir_basename_from_pid
from joblib import Parallel, delayed

import multiprocessing
import pandas as pd
import numpy as np
from multiprocessing import Pool
import scipy.sparse as sp

import regex

seed(1337)
max_train = 25000 # max number of tfidf training documents (chosen randomly), for memory efficiency
max_features = 5000

# read database
db = pickle.load(open(Config.db_path, 'rb'))

# read all text files for all papers into memory

def read_txt_path(p):      
  with open(p, 'r') as f:
    try: # some problems with unicode may arize
      txt = f.read()
    except:
      txt = "" 
  return txt

txt_paths, pids = [], []
n = 0
for pid,j in db.items():
  n += 1
  idvv = '%sv%d' % (j['_rawid'], j['_version'])

  txt_path = os.path.join(Config.txt_dir, dir_basename_from_pid(pid,j)+".txt")

  if os.path.isfile(txt_path): # some pdfs dont translate to txt
    txt = read_txt_path(txt_path)

    if len(txt) > 1000 and len(txt) < 500000: # 500K is VERY conservative upper bound
      txt_paths.append(txt_path) # todo later: maybe filter or something some of them
      pids.append(idvv)
      #print("read %d/%d (%s) with %d chars" % (n, len(db), idvv, len(txt)))
    else:
      print("skipped %d/%d (%s) with %d chars: suspicious!" % (n, len(db), idvv, len(txt)))
      pass
  else:
    print("could not find %s in txt folder." % (txt_path, ))
print("in total read in %d text files out of %d db entries." % (len(txt_paths), len(db)))

# compute tfidf vectors with scikits
v = TfidfVectorizer(input='content',
        encoding='utf-8', decode_error='replace', strip_accents='unicode',
        lowercase=True, analyzer='word', stop_words='english',
        token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',
        ngram_range=(1, 2), max_features = max_features,
        norm='l2', use_idf=True, smooth_idf=True, sublinear_tf=True,
        max_df=1.0, min_df=1)

# create an iterator object to conserve memory
def make_corpus(paths):
  for p in paths:
    yield read_txt_path(p)      

# train
train_txt_paths = list(txt_paths) # duplicate
shuffle(train_txt_paths) # shuffle
train_txt_paths = train_txt_paths[:min(len(train_txt_paths), max_train)] # crop
print("training on %d documents..." % (len(train_txt_paths), ))
train_corpus = make_corpus(train_txt_paths)
v.fit(train_corpus)

# export texts for topic modelling
corpus = make_corpus(txt_paths) # don't forget to rewind
pattern = regex.compile('((?=[^!?.,\ ])\W|\d)+', regex.UNICODE)
clean_txt=(pattern.sub(' ',str(text)[:1000]) for text in corpus)
texts_df=pd.DataFrame(clean_txt, columns=['Text',])
texts_df.to_excel('diego_texts.xlsx',index=True)
del corpus

# https://github.com/rafaelvalero/ParallelTextProcessing/blob/master/parallelizing_text_processing.ipynb
num_cores = multiprocessing.cpu_count()
num_partitions = num_cores-1 # I like to leave some cores for other processes
print('num_partitions',num_partitions)

def parallelize_dataframe(df, func):
    a = np.array_split(df, num_partitions)
    del df
    pool = Pool(num_partitions)
    sparse_mtrx = sp.vstack(pool.map(func, a), format='csr')
    pool.close()
    pool.join()
    return sparse_mtrx

def transform_func(data):
    tfidf_matrix = v.transform(data["text"])
    return tfidf_matrix

# transform
print("transforming %d documents..." % (len(txt_paths), ))
corpus = make_corpus(txt_paths)
data_pd = pd.DataFrame(corpus)
data_pd.rename(columns = {0:'text'},inplace = True)
X = parallelize_dataframe(data_pd, transform_func)

# write full matrix out
out = {}
out['X'] = X # this one is heavy!
print("writing tfidf.p", Config.tfidf_path)
safe_pickle_dump(out, Config.tfidf_path)

# writing lighter metadata information into a separate (smaller) file
out = {}
out['vocab'] = v.vocabulary_
out['idf'] = v._tfidf.idf_
out['pids'] = pids # a full idvv string (id and version number)
out['ptoi'] = { x:i for i,x in enumerate(pids) } # pid to ix in X mapping
print("writing tfidf_meta.p", Config.meta_path)
safe_pickle_dump(out, Config.meta_path)
del out
del data_pd

def compute_batch(i):
  i1 = min(len(pids), i+batch_size)
  xquery = X[i:i1] # BxD
  ds = -np.asarray(np.dot(X, xquery.T)) #NxD * DxB => NxB
  IX = np.argsort(ds, axis=0) # NxB
  for j in range(i1-i):
    sim_dict[pids[i+j]] = [pids[q] for q in list(IX[:50,j])]
  print('%d/%d...' % (i, len(pids)))


print("precomputing nearest neighbor queries in batches...")
X = X.todense().astype(np.float32) # originally it's a sparse matrix
sim_dict = {}
batch_size = 200
Parallel( n_jobs=-1, prefer="threads", verbose=5)(
    delayed(compute_batch)(i) for i in range(0,len(pids),batch_size))

print("writing", Config.sim_path)
safe_pickle_dump(sim_dict, Config.sim_path)
