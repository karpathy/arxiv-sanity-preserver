import os
import pickle

import numpy as np
from sklearn import svm
from sqlite3 import dbapi2 as sqlite3
from utils import safe_pickle_dump, Config


def get_sqldb():
    if not os.path.isfile(Config.database_path):
        sqldb = sqlite3.connect(Config.database_path)
        with open('schema.sql') as fp:
            sqldb.executescript(fp.read())
    else:
        sqldb = sqlite3.connect(Config.database_path)
    sqldb.row_factory = sqlite3.Row  # to return dicts rather than tuples
    return sqldb


def query_db(sqldb, query, args=(), one=False):
    """Queries the database and returns a list of dictionaries."""
    cur = sqldb.execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv


def get_users(sqldb):
    # fetch all users
    users = query_db(sqldb, '''select * from user''')
    print('number of users: ', len(users))
    return users


def get_libs(sqldb, user_id):
    return query_db(sqldb, '''select * from library where user_id = ?''', [user_id])


def get_tfidf():
    meta = pickle.load(open(Config.meta_path, 'rb'))
    out = pickle.load(open(Config.tfidf_path, 'rb'))
    X = out['X']
    X = X.todense().astype(np.float32)

    pids = meta['pids']
    ptoi = meta['ptoi']
    return pids, ptoi, X


def get_user_sim(sqldb, users, meta_pids, ptoi, X, num_recommendations):
    user_sim = {}
    for ii, u in enumerate(users):
        print("%d/%d building an SVM for %s" % (ii, len(users), u['username'].encode('utf-8')))
        user_id = u['user_id']
        user_raw_pids = [x['paper_id'] for x in get_libs(sqldb, user_id)]  # raw pids without version
        user_pid_idx = [ptoi[p] for p in user_raw_pids if p in ptoi]

        if not user_pid_idx:
            continue  # empty library for this user maybe?

        print(user_raw_pids)
        y = np.zeros(X.shape[0])
        for ix in user_pid_idx: y[ix] = 1

        clf = svm.LinearSVC(class_weight='balanced', verbose=False, max_iter=10000, tol=1e-6, C=0.1)
        clf.fit(X, y)
        s = clf.decision_function(X)

        sortix = np.argsort(-s)
        sortix = sortix[:min(num_recommendations, len(sortix))]  # crop paper recommendations to save space
        user_sim[user_id] = [meta_pids[ix] for ix in list(sortix)]

    print('writing', Config.user_sim_path)
    safe_pickle_dump(user_sim, Config.user_sim_path)


def run():
    num_recommendations = 1000  # papers to recommend per user

    sqldb = get_sqldb()
    meta_pids, ptoi, X = get_tfidf()
    get_user_sim(sqldb, get_users(sqldb), meta_pids, ptoi, X, num_recommendations)


if __name__ == '__main__':
    run()
