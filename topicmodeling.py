"""
Reads txt files of all papers and computes tfidf vectors for all papers.
Dumps results to file tfidf.p
"""
import os
import pickle
from random import shuffle, seed

import numpy as np

from time import time
from sklearn.feature_extraction.text import TfidfVectorizer,CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

from utils import Config, safe_pickle_dump

seed(1337)

print("Loading Data...")
t0 = time()
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
        print("read %d/%d (%s)" % (n, len(db), idvv))
    else:
        print("skipped %d/%d (%s)" % (n, len(db), idvv))
  else:
    print("could not find %s in txt folder." % (txt_path, ))
print("in total read in %d text files out of %d db entries." % (len(txt_paths), len(db)))

# create an iterator object to conserve memory
def make_corpus(paths):
  for p in paths:
    with open(p, 'r') as f:
      txt = f.read()
    yield txt

corpus = make_corpus(txt_paths)
print("done in %0.3fs." % (time() - t0))

# n_components = 20
n_top_words = 30

# Extracting term frequency features
print("Extracting tf features for LDA...")
tf_vectorizer = CountVectorizer(strip_accents='unicode',
                                decode_error='replace',
                                analyzer='word',
                                token_pattern=r'\b[a-zA-Z]{3,}\b',
                                max_df=0.95, min_df=2,
                                stop_words='english'
                                )

t0 = time()
tf = tf_vectorizer.fit_transform(corpus)
print("done in %0.3fs." % (time() - t0))
print()

lda = LatentDirichletAllocation(n_components=100,
                                learning_method='batch',
                                max_iter=1000)

# Fit LDA model
print("Fitting LDA models... ")
t0 = time()
lda.fit(tf)
print("done in %0.3fs." % (time() - t0))
print("\nTopics in LDA model:")
tf_feature_names = tf_vectorizer.get_feature_names()

def print_top_words(model, feature_names, n_top_words):
    for topic_idx, topic in enumerate(model.components_):
        message = "Topic #%d: " % topic_idx
        message += " ".join([feature_names[i]
                             for i in topic.argsort()[:-n_top_words - 1:-1]])
        print(message)
    print()

print_top_words(lda, tf_feature_names, n_top_words)

print("writing", './ldamodel.p')
safe_pickle_dump(lda, './ldamodel.p')