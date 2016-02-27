from sqlite3 import dbapi2 as sqlite3
import cPickle as pickle
import numpy as np
import json
import time
import dateutil.parser
import argparse
from random import shuffle
import re
import os
from sklearn import svm

DATABASE = 'as.db'
sqldb = sqlite3.connect(DATABASE)
sqldb.row_factory = sqlite3.Row # to return dicts rather than tuples

def query_db(query, args=(), one=False):
  """Queries the database and returns a list of dictionaries."""
  cur = sqldb.execute(query, args)
  rv = cur.fetchall()
  return (rv[0] if rv else None) if one else rv

users = query_db('''select * from user''')
for u in users:
  print u
print 'number of users: ', len(users)
print 'PRESS ENTER TO CONTINUE'
raw_input()

def strip_version(idstr):
  """ identity function if arxiv id has no version, otherwise strips it. """
  parts = idstr.split('v')
  return parts[0]

# fetch the tfidf matrix
meta = pickle.load(open("tfidf_meta.p", "rb"))
out = pickle.load(open("tfidf.p", "rb"))
X = out['X']
X = X.todense()

xtoi = { strip_version(x):i for x,i in meta['ptoi'].iteritems() }

user_sim = {}
for u in users:
  print 'building an SVM for ' + u['username']
  uid = u['user_id']
  lib = query_db('''select * from library where user_id = ?''', [uid])
  pids = [x['paper_id'] for x in lib] # raw pids without version
  posix = [xtoi[p] for p in pids if p in xtoi]
  
  if not posix:
    continue # empty library for this user maybe?

  print pids
  y = np.zeros(X.shape[0])
  for ix in posix:
    y[ix] = 1

  #__init__(penalty='l2', loss='squared_hinge', dual=True, tol=0.0001, C=1.0, multi_class='ovr', fit_intercept=True, intercept_scaling=1, class_weight=None, verbose=0, random_state=None, max_iter=1000)[source]
  clf = svm.LinearSVC(class_weight='auto', verbose=True, max_iter=10000, tol=1e-6, C=1)
  clf.fit(X,y)
  s = clf.decision_function(X)

  sortix = np.argsort(-s)
  user_sim[uid] = [strip_version(meta['pids'][ix]) for ix in list(sortix)]

print 'writing user_sim.p'
pickle.dump(user_sim, open("user_sim.p", "wb"))
