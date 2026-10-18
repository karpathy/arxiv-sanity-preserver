"""
Flask server backend

ideas:
- allow delete of tags
- unify all different pages into single search filter sort interface
- special single-image search just for paper similarity
"""

import os
import re
import time
from random import shuffle

import numpy as np
from sklearn import svm

from flask import Flask, request, redirect, url_for
from flask import render_template
from flask import g # global session-level object
from flask import session

from aslite.db import get_papers_db, get_metas_db, get_tags_db, get_last_active_db, get_email_db
from aslite.db import load_features

# -----------------------------------------------------------------------------
# inits and globals

RET_NUM = 25 # number of papers to return per page

app = Flask(__name__)

# set the secret key so we can cryptographically sign cookies and maintain sessions
if os.path.isfile('secret_key.txt'):
    # example of generating a good key on your system is:
    # import secrets; secrets.token_urlsafe(16)
    sk = open('secret_key.txt').read().strip()
else:
    print("WARNING: no secret key found, using default devkey")
    sk = 'devkey'
app.secret_key = sk

# -----------------------------------------------------------------------------
# globals that manage the (lazy) loading of various state for a request

def get_tags():
    if g.user is None:
        return {}
    if not hasattr(g, '_tags'):
        with get_tags_db() as tags_db:
            tags_dict = tags_db[g.user] if g.user in tags_db else {}
        g._tags = tags_dict
    return g._tags

def get_papers():
    if not hasattr(g, '_pdb'):
        g._pdb = get_papers_db()
    return g._pdb

def get_metas():
    if not hasattr(g, '_mdb'):
        g._mdb = get_metas_db()
    return g._mdb

@app.before_request
def before_request():
    g.user = session.get('user', None)

    # record activity on this user so we can reserve periodic
    # recommendations heavy compute only for active users
    if g.user:
        with get_last_active_db(flag='c') as last_active_db:
            last_active_db[g.user] = int(time.time())

@app.teardown_request
def close_connection(error=None):
    # close any opened database connections
    if hasattr(g, '_pdb'):
        g._pdb.close()
    if hasattr(g, '_mdb'):
        g._mdb.close()

# -----------------------------------------------------------------------------
# ranking utilities for completing the search/rank/filter requests

def render_pid(pid):
    # render a single paper with just the information we need for the UI
    pdb = get_papers()
    tags = get_tags()
    thumb_path = 'static/thumb/' + pid + '.jpg'
    thumb_url = thumb_path if os.path.isfile(thumb_path) else ''
    d = pdb[pid]
    return dict(
        weight = 0.0,
        id = d['_id'],
        title = d['title'],
        time = d['_time_str'],
        authors = ', '.join(a['name'] for a in d['authors']),
        tags = ', '.join(t['term'] for t in d['tags']),
        utags = [t for t, pids in tags.items() if pid in pids],
        summary = d['summary'],
        thumb_url = thumb_url,
    )

def random_rank():
    mdb = get_metas()
    pids = list(mdb.keys())
    shuffle(pids)
    scores = [0 for _ in pids]
    return pids, scores

def time_rank():
    mdb = get_metas()
    ms = sorted(mdb.items(), key=lambda kv: kv[1]['_time'], reverse=True)
    tnow = time.time()
    pids = [k for k, v in ms]
    scores = [(tnow - v['_time'])/60/60/24 for k, v in ms] # time delta in days
    return pids, scores

def svm_rank(tags: str = '', pid: str = '', C: float = 0.01):

    # tag can be one tag or a few comma-separated tags or 'all' for all tags we have in db
    # pid can be a specific paper id to set as positive for a kind of nearest neighbor search
    if not (tags or pid):
        return [], [], []

    # load all of the features
    features = load_features()
    x, pids = features['x'], features['pids']
    n, d = x.shape
    ptoi, itop = {}, {}
    for i, p in enumerate(pids):
        ptoi[p] = i
        itop[i] = p

    # construct the positive set
    y = np.zeros(n, dtype=np.float32)
    if pid:
        y[ptoi[pid]] = 1.0
    elif tags:
        tags_db = get_tags()
        tags_filter_to = tags_db.keys() if tags == 'all' else set(tags.split(','))
        for tag, pids in tags_db.items():
            if tag in tags_filter_to:
                for pid in pids:
                    y[ptoi[pid]] = 1.0

    if y.sum() == 0:
        return [], [], [] # there are no positives?

    # classify
    clf = svm.LinearSVC(class_weight='balanced', verbose=False, max_iter=10000, tol=1e-6, C=C)
    clf.fit(x, y)
    s = clf.decision_function(x)
    sortix = np.argsort(-s)
    pids = [itop[ix] for ix in sortix]
    scores = [100*float(s[ix]) for ix in sortix]

    # get the words that score most positively and most negatively for the svm
    ivocab = {v:k for k,v in features['vocab'].items()} # index to word mapping
    weights = clf.coef_[0] # (n_features,) weights of the trained svm
    sortix = np.argsort(-weights)
    words = []
    for ix in list(sortix[:40]) + list(sortix[-20:]):
        words.append({
            'word': ivocab[ix],
            'weight': weights[ix],
        })

    return pids, scores, words

def search_rank(q: str = ''):
    if not q:
        return [], [] # no query? no results
    qs = q.lower().strip().split() # split query by spaces and lowercase

    pdb = get_papers()
    match = lambda s: sum(min(3, s.lower().count(qp)) for qp in qs)
    matchu = lambda s: sum(int(s.lower().count(qp) > 0) for qp in qs)
    pairs = []
    for pid, p in pdb.items():
        score = 0.0
        score += 10.0 * matchu(' '.join([a['name'] for a in p['authors']]))
        score += 20.0 * matchu(p['title'])
        score += 1.0 * match(p['summary'])
        if score > 0:
            pairs.append((score, pid))

    pairs.sort(reverse=True)
    pids = [p[1] for p in pairs]
    scores = [p[0] for p in pairs]
    return pids, scores

# -----------------------------------------------------------------------------
# primary application endpoints

def default_context():
    # any global context across all pages, e.g. related to the current user
    context = {}
    context['user'] = g.user if g.user is not None else ''
    return context

@app.route('/', methods=['GET'])
def main():

    # default settings
    default_rank = 'time'
    default_tags = ''
    default_time_filter = ''
    default_skip_have = 'no'

    # override variables with any provided options via the interface
    opt_rank = request.args.get('rank', default_rank) # rank type. search|tags|pid|time|random
    opt_q = request.args.get('q', '') # search request in the text box
    opt_tags = request.args.get('tags', default_tags)  # tags to rank by if opt_rank == 'tag'
    opt_pid = request.args.get('pid', '')  # pid to find nearest neighbors to
    opt_time_filter = request.args.get('time_filter', default_time_filter) # number of days to filter by
    opt_skip_have = request.args.get('skip_have', default_skip_have) # hide papers we already have?
    opt_svm_c = request.args.get('svm_c', '') # svm C parameter
    opt_page_number = request.args.get('page_number', '1') # page number for pagination

    # if a query is given, override rank to be of type "search"
    # this allows the user to simply hit ENTER in the search field and have the correct thing happen
    if opt_q:
        opt_rank = 'search'

    # try to parse opt_svm_c into something sensible (a float)
    try:
        C = float(opt_svm_c)
    except ValueError:
        C = 0.01 # sensible default, i think

    # rank papers: by tags, by time, by random
    words = [] # only populated in the case of svm rank
    if opt_rank == 'search':
        pids, scores = search_rank(q=opt_q)
    elif opt_rank == 'tags':
        pids, scores, words = svm_rank(tags=opt_tags, C=C)
    elif opt_rank == 'pid':
        pids, scores, words = svm_rank(pid=opt_pid, C=C)
    elif opt_rank == 'time':
        pids, scores = time_rank()
    elif opt_rank == 'random':
        pids, scores = random_rank()
    else:
        raise ValueError("opt_rank %s is not a thing" % (opt_rank, ))

    # filter by time
    if opt_time_filter:
        mdb = get_metas()
        kv = {k:v for k,v in mdb.items()} # read all of metas to memory at once, for efficiency
        tnow = time.time()
        deltat = int(opt_time_filter)*60*60*24 # allowed time delta in seconds
        keep = [i for i,pid in enumerate(pids) if (tnow - kv[pid]['_time']) < deltat]
        pids, scores = [pids[i] for i in keep], [scores[i] for i in keep]

    # optionally hide papers we already have
    if opt_skip_have == 'yes':
        tags = get_tags()
        have = set().union(*tags.values())
        keep = [i for i,pid in enumerate(pids) if pid not in have]
        pids, scores = [pids[i] for i in keep], [scores[i] for i in keep]

    # crop the number of results to RET_NUM, and paginate
    try:
        page_number = max(1, int(opt_page_number))
    except ValueError:
        page_number = 1
    start_index = (page_number - 1) * RET_NUM # desired starting index
    end_index = min(start_index + RET_NUM, len(pids)) # desired ending index
    pids = pids[start_index:end_index]
    scores = scores[start_index:end_index]

    # render all papers to just the information we need for the UI
    papers = [render_pid(pid) for pid in pids]
    for i, p in enumerate(papers):
        p['weight'] = float(scores[i])

    # build the current tags for the user, and append the special 'all' tag
    tags = get_tags()
    rtags = [{'name':t, 'n':len(pids)} for t, pids in tags.items()]
    if rtags:
        rtags.append({'name': 'all'})

    # build the page context information and render
    context = default_context()
    context['papers'] = papers
    context['tags'] = rtags
    context['words'] = words
    context['words_desc'] = "Here are the top 40 most positive and bottom 20 most negative weights of the SVM. If they don't look great then try tuning the regularization strength hyperparameter of the SVM, svm_c, above. Lower C is higher regularization."
    context['gvars'] = {}
    context['gvars']['rank'] = opt_rank
    context['gvars']['tags'] = opt_tags
    context['gvars']['pid'] = opt_pid
    context['gvars']['time_filter'] = opt_time_filter
    context['gvars']['skip_have'] = opt_skip_have
    context['gvars']['search_query'] = opt_q
    context['gvars']['svm_c'] = str(C)
    context['gvars']['page_number'] = str(page_number)
    return render_template('index.html', **context)

@app.route('/inspect', methods=['GET'])
def inspect():

    # fetch the paper of interest based on the pid
    pid = request.args.get('pid', '')
    pdb = get_papers()
    if pid not in pdb:
        return "error, malformed pid" # todo: better error handling

    # load the tfidf vectors, the vocab, and the idf table
    features = load_features()
    x = features['x']
    idf = features['idf']
    ivocab = {v:k for k,v in features['vocab'].items()}
    pix = features['pids'].index(pid)
    wixs = np.flatnonzero(np.asarray(x[pix].todense()))
    words = []
    for ix in wixs:
        words.append({
            'word': ivocab[ix],
            'weight': float(x[pix, ix]),
            'idf': float(idf[ix]),
        })
    words.sort(key=lambda w: w['weight'], reverse=True)

    # package everything up and render
    paper = render_pid(pid)
    context = default_context()
    context['paper'] = paper
    context['words'] = words
    context['words_desc'] = "The following are the tokens and their (tfidf) weight in the paper vector. This is the actual summary that feeds into the SVM to power recommendations, so hopefully it is good and representative!"
    return render_template('inspect.html', **context)

@app.route('/profile')
def profile():
    context = default_context()
    with get_email_db() as edb:
        email = edb.get(g.user, '')
        context['email'] = email
    return render_template('profile.html', **context)

@app.route('/stats')
def stats():
    context = default_context()
    mdb = get_metas()
    kv = {k:v for k,v in mdb.items()} # read all of metas to memory at once, for efficiency
    times = [v['_time'] for v in kv.values()]
    tstr = lambda t: time.strftime('%b %d %Y', time.localtime(t))

    context['num_papers'] = len(kv)
    if len(kv) > 0:
        context['earliest_paper'] = tstr(min(times))
        context['latest_paper'] = tstr(max(times))
    else:
        context['earliest_paper'] = 'N/A'
        context['latest_paper'] = 'N/A'

    # count number of papers from various time deltas to now
    tnow = time.time()
    for thr in [1, 6, 12, 24, 48, 72, 96]:
        context['thr_%d' % thr] = len([t for t in times if t > tnow - thr*60*60])

    return render_template('stats.html', **context)

@app.route('/about')
def about():
    context = default_context()
    return render_template('about.html', **context)

# -----------------------------------------------------------------------------
# tag related endpoints: add, delete tags for any paper

@app.route('/add/<pid>/<tag>')
def add(pid=None, tag=None):
    if g.user is None:
        return "error, not logged in"
    if tag == 'all':
        return "error, cannot add the protected tag 'all'"
    elif tag == 'null':
        return "error, cannot add the protected tag 'null'"

    with get_tags_db(flag='c') as tags_db:

        # create the user if we don't know about them yet with an empty library
        if not g.user in tags_db:
            tags_db[g.user] = {}

        # fetch the user library object
        d = tags_db[g.user]

        # add the paper to the tag
        if tag not in d:
            d[tag] = set()
        d[tag].add(pid)

        # write back to database
        tags_db[g.user] = d

    print("added paper %s to tag %s for user %s" % (pid, tag, g.user))
    return "ok: " + str(d) # return back the user library for debugging atm

@app.route('/sub/<pid>/<tag>')
def sub(pid=None, tag=None):
    if g.user is None:
        return "error, not logged in"

    with get_tags_db(flag='c') as tags_db:

        # if the user doesn't have any tags, there is nothing to do
        if not g.user in tags_db:
            return "user has no library of tags ¯\_(ツ)_/¯"

        # fetch the user library object
        d = tags_db[g.user]

        # add the paper to the tag
        if tag not in d:
            return "user doesn't have the tag %s" % (tag, )
        else:
            if pid in d[tag]:

                # remove this pid from the tag
                d[tag].remove(pid)

                # if this was the last paper in this tag, also delete the tag
                if len(d[tag]) == 0:
                    del d[tag]

                # write back the resulting dict to database
                tags_db[g.user] = d
                return "ok removed pid %s from tag %s" % (pid, tag)
            else:
                return "user doesn't have paper %s in tag %s" % (pid, tag)

@app.route('/del/<tag>')
def delete_tag(tag=None):
    if g.user is None:
        return "error, not logged in"

    with get_tags_db(flag='c') as tags_db:

        if g.user not in tags_db:
            return "user does not have a library"

        d = tags_db[g.user]

        if tag not in d:
            return "user does not have this tag"

        # delete the tag
        del d[tag]

        # write back to database
        tags_db[g.user] = d

    print("deleted tag %s for user %s" % (tag, g.user))
    return "ok: " + str(d) # return back the user library for debugging atm

# -----------------------------------------------------------------------------
# endpoints to log in and out

@app.route('/login', methods=['POST'])
def login():

    # the user is logged out but wants to log in, ok
    if g.user is None and request.form['username']:
        username = request.form['username']
        if len(username) > 0: # one more paranoid check
            session['user'] = username

    return redirect(url_for('profile'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('profile'))

# -----------------------------------------------------------------------------
# user settings and configurations

@app.route('/register_email', methods=['POST'])
def register_email():
    email = request.form['email']

    if g.user:
        # do some basic input validation
        proper_email = re.match(r'^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$', email, re.IGNORECASE)
        if email == '' or proper_email: # allow empty email, meaning no email
            # everything checks out, write to the database
            with get_email_db(flag='c') as edb:
                edb[g.user] = email

    return redirect(url_for('profile'))
