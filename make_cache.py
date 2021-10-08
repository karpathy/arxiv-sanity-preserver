"""
computes various cache things on top of db.py so that the server
(running from serve.py) can start up and serve faster when restarted.

this script should be run whenever db.p is updated, and 
creates db2.p, which can be read by the server.
"""

import time
import pickle

from sqlite3 import dbapi2 as sqlite3
from utils import safe_pickle_dump, Config, to_datetime, PAPER_INIT_YEAR, to_struct_time


def load_dbs():
    sqldb = sqlite3.connect(Config.database_path)
    sqldb.row_factory = sqlite3.Row  # to return dicts rather than tuples

    print('loading the paper database', Config.db_path)
    db = pickle.load(open(Config.db_path, 'rb'))

    print('loading tfidf_meta', Config.meta_path)
    meta = pickle.load(open(Config.meta_path, "rb"))

    return sqldb, db, meta


def loop_db_for_infos(db, vocab, idf):
    print('looping db for information...')
    paper_min_published_time = time.mktime(to_struct_time(PAPER_INIT_YEAR))
    paper_max_published_time = time.time()
    # preparing date-pid-tuple for descend datas
    date_pid_tuple = []
    # just for faster search
    search_dict = {}
    for pid, p in db.items():
        # add time score weight to db to make a better searching result
        tt = time.mktime(p['updated_parsed'])
        p['tscore'] = (tt - paper_min_published_time) / (paper_max_published_time - paper_min_published_time)

        date_pid_tuple.append((to_datetime(p['updated_parsed']), pid))

        dict_title = makedict(p['title'], vocab, idf, forceidf=5, scale=3)
        dict_authors = makedict(' '.join(x['name'] for x in p['authors']), vocab, idf, forceidf=5)
        dict_categories = {x['term'].lower(): 5 for x in p['tags']}
        if 'and' in dict_authors:
            # special case for "and" handling in authors list
            del dict_authors['and']
        dict_summary = makedict(p['summary'], vocab, idf)
        search_dict[pid] = merge_dicts([dict_title, dict_authors, dict_categories, dict_summary])

    date_pid_tuple.sort(reverse=True, key=lambda x: x[0])
    date_sorted_pids = [sp[1] for sp in date_pid_tuple]

    return db, date_sorted_pids, search_dict


def get_top_papers(sqldb):
    # compute top papers in peoples' libraries
    print('computing top papers...')
    libs = sqldb.execute('''select * from library''').fetchall()
    counts = {}
    for lib in libs:
        pid = lib['paper_id']
        counts[pid] = counts.get(pid, 0) + 1
    top_paper_counts = sorted([(v, k) for k, v in counts.items() if v > 0], reverse=True)
    return [q[1] for q in top_paper_counts]


def makedict(s, vocab, idf, forceidf=None, scale=1.0):
    # some utilities for creating a search index for faster search
    punc = "'!\"#$%&\'()*+,./:;<=>?@[\\]^_`{|}~'"  # removed hyphen from string.punctuation
    trans_table = {ord(c): None for c in punc}

    words = set(s.lower().translate(trans_table).strip().split())
    idfd = {}
    for w in words:  # todo: if we're using bigrams in vocab then this won't search over them
        if forceidf is None:
            if w in vocab:
                # we have idf for this
                idfval = idf[vocab[w]] * scale
            else:
                idfval = 1.0 * scale  # assume idf 1.0 (low)
        else:
            idfval = forceidf
        idfd[w] = idfval
    return idfd


def merge_dicts(dlist):
    m = {}
    for d in dlist:
        for k, v in d.items():
            m[k] = m.get(k, 0) + v
    return m


def save_cache(cache, updated_db):
    # save the cache
    print('writing', Config.serve_cache_path)
    safe_pickle_dump(cache, Config.serve_cache_path)
    print('writing', Config.db_serve_path)
    safe_pickle_dump(updated_db, Config.db_serve_path)


def run():
    sqldb, db, meta = load_dbs()
    vocab, idf = meta['vocab'], meta['idf']

    top_sorted_pids = get_top_papers(sqldb)
    updated_db, date_sorted_pids, search_dict = loop_db_for_infos(db, vocab, idf)

    cache = {"top_sorted_pids": top_sorted_pids, "date_sorted_pids": date_sorted_pids, "search_dict": search_dict}

    save_cache(cache, updated_db)


if __name__ == "__main__":
    run()
