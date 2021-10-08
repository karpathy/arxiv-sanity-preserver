"""
Reads txt files of all papers and computes tfidf vectors for all papers.
Dumps results to file tfidf.p
"""
import collections
import os
import pickle
import re
import numpy as np
from random import shuffle, seed
from sklearn.feature_extraction.text import TfidfVectorizer
from utils import Config, safe_pickle_dump, is_first_day_of_half_year


def load_pids():
    print('loading pids if exists:%s' % Config.meta_path)

    try:
        if os.path.exists(Config.meta_path):
            meta = pickle.load(open(Config.meta_path, 'rb'))
            pids = meta['pids']
        else:
            pids = []
    except Exception as e:
        print('error loading existing pids:')
        print(e)
        print('starting from an empty pids')
        pids = []

    return pids


def load_vocab():
    print('loading vocab if exists:%s' % Config.meta_path)

    try:
        if os.path.exists(Config.meta_path):
            meta = pickle.load(open(Config.meta_path, 'rb'))
            vocab = meta['vocab']
        else:
            vocab = None
    except Exception as e:
        print('error loading existing vocab:')
        print(e)
        print('starting from an empty vocab')
        vocab = None

    return vocab


def load_sim_dict():
    print('loading sim_dict if exists:%s' % Config.sim_path)

    try:
        if os.path.exists(Config.sim_path):
            sim_dict = pickle.load(open(Config.sim_path, 'rb'))
        else:
            sim_dict = {}
    except Exception as e:
        print('error loading existing sim_dict:')
        print(e)
        print('starting from an empty sim_dict')
        sim_dict = {}

    return sim_dict


def clear_cache():
    if os.path.exists(Config.meta_path):
        os.remove(Config.meta_path)
    if os.path.exists(Config.tfidf_path):
        os.remove(Config.tfidf_path)
    if os.path.exists(Config.sim_path):
        os.remove(Config.sim_path)


# read all text files for all papers into memory,keep idx not change
def data_preparing():
    db = pickle.load(open(Config.db_path, 'rb'))
    db = collections.OrderedDict(sorted(db.items(), reverse=True))

    handled = 0
    txts, pids, new_pids = [], load_pids(), []
    tmp_pids = set(pids)
    print('adding new pids...')
    for pid, _ in db.items():
        set_len_before = len(tmp_pids)
        tmp_pids.add(pid)
        if set_len_before != len(tmp_pids):
            pids.append(pid)
            new_pids.append(pid)
            handled += 1
        if handled != 0 and handled % 10000 == 0:
            print('new %d pids added' % (handled))
    print('new %d pids added' % (handled))
    handled = 0
    for pid in pids:
        handled += 1

        j = db[pid]
        title = j['title']
        authors = ' '.join([re.sub('\\s', '', re.sub('[^a-zA-Z]', '', x['name'])) for x in j['authors']])
        terms = ' '.join([re.sub(';', ' ', re.sub('[^a-zA-Z0-9.;]', '', x['term'])) for x in j['tags']])
        summary = j['summary']
        txts.append(title + ' ' + authors + ' ' + terms + ' ' + summary)
        print("read %d/%d (%s)" % (handled, len(db), pid))

    return txts, pids, new_pids


def get_tfidf(txts, pids, max_features, max_train):
    vocab = load_vocab()

    tfidf_vec = TfidfVectorizer(input='content',
                                encoding='utf-8', decode_error='replace', strip_accents='unicode',
                                lowercase=True, analyzer='word', stop_words='english',
                                token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',
                                ngram_range=(1, 2), max_features=max_features,
                                norm='l2', use_idf=True, smooth_idf=True, sublinear_tf=True,
                                max_df=1.0, min_df=1, vocabulary=vocab)

    # train
    train_txts = list(txts)  # duplicate
    shuffle(train_txts)  # shuffle
    train_txts = train_txts[:min(len(train_txts), max_train)]  # crop
    print("training on %d documents..." % (len(train_txts),))
    tfidf_vec.fit(train_txts)
    # writing lighter metadata information into a separate (smaller) file
    out = {'vocab': tfidf_vec.vocabulary_, 'idf': tfidf_vec._tfidf.idf_, 'pids': pids,
           'ptoi': {x: i for i, x in enumerate(pids)}}
    print("writing", Config.meta_path)
    safe_pickle_dump(out, Config.meta_path)

    # transform
    print("transforming %d documents..." % (len(txts),))
    X = tfidf_vec.transform(txts)
    # write full matrix out
    out = {}
    out['X'] = X  # this one is heavy!
    print("writing", Config.tfidf_path)
    safe_pickle_dump(out, Config.tfidf_path)
    return X


# ignore affect of idf change
def calc_sim(X, cur_pids_len, new_pids, max_sim=50, batch_size=200, scale=100000):
    print("precomputing nearest neighbor queries in batches...")
    sim_dict = load_sim_dict()

    # update old
    base = cur_pids_len - len(new_pids)
    for i in range(0, base, batch_size):
        i1 = min(base, i + batch_size)
        print('update similarity %d → %d' % (i, i1))

        xquery = X[i:i1]  # BxD
        ds = -np.asarray(np.dot(X[base:], xquery.T) * scale, dtype=np.int32)  # NxD * DxB => NxB

        partition_len = min(len(ds), max_sim)
        indexes = np.argpartition(ds, partition_len - 1, axis=0)  # 2th parameter is partition idx so minus 1

        for j in range(i1 - i):
            topk_idx = indexes[:partition_len, j]
            sims = (sim_dict[i + j] + [(q + base, ds[q][j]) for q in topk_idx])
            sim_dict[i + j] = sorted(sims, key=lambda x: x[1])[:max_sim]

    # add new
    for i in range(base, cur_pids_len, batch_size):
        i1 = min(cur_pids_len, i + batch_size)
        print('add similarity %d → %d' % (i, i1))

        xquery = X[i:i1]  # BxD
        ds = -np.asarray(np.dot(X, xquery.T) * scale, dtype=np.int32)  # NxD * DxB => NxB

        partition_len = min(len(ds), max_sim)
        indexes = np.argpartition(ds, partition_len - 1, axis=0)  # 2th parameter is partition idx so minus 1

        for j in range(i1 - i):
            topk_idx = indexes[:partition_len, j]
            sims = [(q, ds[q][j]) for q in topk_idx]
            sim_dict[i + j] = sorted(sims, key=lambda x: x[1])

    print("writing", Config.sim_path)
    safe_pickle_dump(sim_dict, Config.sim_path)


def run():
    seed(1337)
    max_train = 5000  # max number of tfidf training documents (chosen randomly), for memory efficiency
    max_features = 5000

    # fix update not consider idf effect for old data every half year
    if is_first_day_of_half_year():
        clear_cache()

    txts, pids, new_pids = data_preparing()

    if len(new_pids) > 0:
        X = get_tfidf(txts, pids, max_features, max_train)
        X = X.todense()  # originally it's a sparse matrix
        calc_sim(X, len(pids), new_pids)


if __name__ == "__main__":
    run()
