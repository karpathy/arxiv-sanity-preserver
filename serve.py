import os
import json
import time
import pickle
import dateutil.parser
import argparse
from random import shuffle

import numpy as np
from sqlite3 import dbapi2 as sqlite3
from hashlib import md5
from flask import Flask, request, session, url_for, redirect, \
     render_template, abort, g, flash, _app_ctx_stack
from flask_limiter import Limiter
from werkzeug import check_password_hash, generate_password_hash

from utils import safe_pickle_dump, strip_version, isvalidid, Config

# various globals
# -----------------------------------------------------------------------------

# database configuration
if os.path.isfile('secret_key.txt'):
  SECRET_KEY = open('secret_key.txt', 'r').read()
else:
  SECRET_KEY = 'devkey, should be in a file'
app = Flask(__name__)
app.config.from_object(__name__)
limiter = Limiter(app, global_limits=["100 per hour", "20 per minute"])

SEARCH_DICT = {}

# -----------------------------------------------------------------------------
# utilities for database interactions 
# -----------------------------------------------------------------------------
# to initialize the database: sqlite3 as.db < schema.sql
def connect_db():
  sqlite_db = sqlite3.connect(Config.database_path)
  sqlite_db.row_factory = sqlite3.Row # to return dicts rather than tuples
  return sqlite_db

def query_db(query, args=(), one=False):
  """Queries the database and returns a list of dictionaries."""
  cur = g.db.execute(query, args)
  rv = cur.fetchall()
  return (rv[0] if rv else None) if one else rv

def get_user_id(username):
  """Convenience method to look up the id for a username."""
  rv = query_db('select user_id from user where username = ?',
                [username], one=True)
  return rv[0] if rv else None

def get_username(user_id):
  """Convenience method to look up the username for a user."""
  rv = query_db('select username from user where user_id = ?',
                [user_id], one=True)
  return rv[0] if rv else None

# -----------------------------------------------------------------------------
# connection handlers
# -----------------------------------------------------------------------------

@app.before_request
def before_request():
  # this will always request database connection, even if we dont end up using it ;\
  g.db = connect_db()
  # retrieve user object from the database if user_id is set
  g.user = None
  if 'user_id' in session:
    g.user = query_db('select * from user where user_id = ?',
                      [session['user_id']], one=True)

@app.teardown_request
def teardown_request(exception):
  db = getattr(g, 'db', None)
  if db is not None:
    db.close()

# -----------------------------------------------------------------------------
# search/sort functionality
# -----------------------------------------------------------------------------
def date_sort():
  scores = []
  for pid,p in db.items():
    timestruct = dateutil.parser.parse(p['updated'])
    p['time_updated'] = int(timestruct.strftime("%s")) # store in struct for future convenience
    timestruct = dateutil.parser.parse(p['published'])
    p['time_published'] = int(timestruct.strftime("%s")) # store in struct for future convenience
    scores.append((p['time_updated'], p))
  scores.sort(reverse=True, key=lambda x: x[0])
  out = [sp[1] for sp in scores]
  return out

def papers_search(qraw):
  qparts = qraw.lower().strip().split() # split by spaces
  # use reverse index and accumulate scores
  scores = []
  for pid,p in db.items():
    score = sum(SEARCH_DICT[pid].get(q,0) for q in qparts)
    if score == 0:
      continue # no match whatsoever, dont include
    # give a small boost to more recent papers
    score += 0.0001*p['tscore']
    scores.append((score, p))
  scores.sort(reverse=True, key=lambda x: x[0]) # descending
  out = [x[1] for x in scores if x[0] > 0]
  return out

def papers_similar(pid):
  rawpid = strip_version(pid)

  # check if we have this paper at all, otherwise return empty list
  if not rawpid in db: 
    return []

  # check if we have distances to this specific version of paper id (includes version)
  if pid in sim_dict:
    # good, simplest case: lets return the papers
    return [db[strip_version(k)] for k in sim_dict[pid]]
  else:
    # ok we don't have this specific version. could be a stale URL that points to, 
    # e.g. v1 of a paper, but due to an updated version of it we only have v2 on file
    # now. We want to use v2 in that case.
    # lets try to retrieve the most recent version of this paper we do have
    kok = [k for k in sim_dict if rawpid in k]
    if kok:
      # ok we have at least one different version of this paper, lets use it instead
      id_use_instead = kok[0]
      return [db[strip_version(k)] for k in sim_dict[id_use_instead]]
    else:
      # return just the paper. we dont have similarities for it for some reason
      return [db[rawpid]]

def papers_from_library():
  out = []
  if g.user:
    # user is logged in, lets fetch their saved library data
    uid = session['user_id']
    user_library = query_db('''select * from library where user_id = ?''', [uid])
    libids = [strip_version(x['paper_id']) for x in user_library]
    out = [db[x] for x in libids]
    out = sorted(out, key=lambda k: k['updated'], reverse=True)
  return out

def papers_from_svm(recent_days=None):
  out = []
  if g.user:

    uid = session['user_id']
    if not uid in user_sim:
      return []
    
    # we want to exclude papers that are already in user library from the result, so fetch them.
    user_library = query_db('''select * from library where user_id = ?''', [uid])
    libids = {strip_version(x['paper_id']) for x in user_library}

    plist = user_sim[uid]
    out = [db[x] for x in plist if not x in libids]

    if recent_days is not None:
      # filter as well to only most recent papers
      curtime = int(time.time()) # in seconds
      out = [x for x in out if curtime - x['time_published'] < recent_days*24*60*60]

  return out

def papers_filter_version(papers, v):
  if v != '1': 
    return papers # noop
  intv = int(v)
  filtered = [p for p in papers if p['_version'] == intv]
  return filtered

def encode_json(ps, n=10, send_images=True, send_abstracts=True):

  libids = set()
  if g.user:
    # user is logged in, lets fetch their saved library data
    uid = session['user_id']
    user_library = query_db('''select * from library where user_id = ?''', [uid])
    libids = {strip_version(x['paper_id']) for x in user_library}

  ret = []
  for i in range(min(len(ps),n)):
    p = ps[i]
    idvv = '%sv%d' % (p['_rawid'], p['_version'])
    struct = {}
    struct['title'] = p['title']
    struct['pid'] = idvv
    struct['category'] = p['arxiv_primary_category']['term']
    struct['authors'] = [a['name'] for a in p['authors']]
    struct['link'] = p['link']
    struct['in_library'] = 1 if p['_rawid'] in libids else 0
    if send_abstracts:
      struct['abstract'] = p['summary']
    if send_images:
      struct['img'] = '/static/thumbs/' + idvv + '.pdf.jpg'
    struct['tags'] = [t['term'] for t in p['tags']]
    
    timestruct = dateutil.parser.parse(p['updated'])
    struct['published_time'] = '%s/%s/%s' % (timestruct.month, timestruct.day, timestruct.year)
    timestruct = dateutil.parser.parse(p['published'])
    struct['originally_published_time'] = '%s/%s/%s' % (timestruct.month, timestruct.day, timestruct.year)

    cc = p.get('arxiv_comment', '')
    if len(cc) > 100:
      cc = cc[:100] + '...' # crop very long comments
    struct['comment'] = cc

    ret.append(struct)
  return ret

# -----------------------------------------------------------------------------
# flask request handling
# -----------------------------------------------------------------------------

def default_context(papers, **kws):
  top_papers = encode_json(papers, args.num_results)
  ans = dict(papers=top_papers, numresults=len(papers), totpapers=len(db), msg='')
  ans.update(kws)
  return ans

@app.route("/")
def intmain():
  vstr = request.args.get('vfilter', 'all')
  papers = DATE_SORTED_PAPERS # precomputed
  papers = papers_filter_version(papers, vstr)
  ctx = default_context(papers, render_format='recent',
                        msg='Showing most recent Arxiv papers:')
  return render_template('main.html', **ctx)

@app.route("/<request_pid>")
def rank(request_pid=None):
  if not isvalidid(request_pid):
    return '' # these are requests for icons, things like robots.txt, etc
  papers = papers_similar(request_pid)
  ctx = default_context(papers, render_format='paper')
  return render_template('main.html', **ctx)

@app.route("/search", methods=['GET'])
def search():
  q = request.args.get('q', '') # get the search request
  papers = papers_search(q) # perform the query and get sorted documents
  ctx = default_context(papers, render_format="search")
  return render_template('main.html', **ctx)

@app.route('/recommend', methods=['GET'])
def recommend():
  """ return user's svm sorted list """
  ttstr = request.args.get('timefilter', 'week') # default is week
  vstr = request.args.get('vfilter', 'all') # default is all (no filter)
  legend = {'day':1, '3days':3, 'week':7, 'month':30, 'year':365}
  tt = legend.get(ttstr, None)
  papers = papers_from_svm(recent_days=tt)
  papers = papers_filter_version(papers, vstr)
  ctx = default_context(papers, render_format='recommend',
                        msg='Recommended papers: (based on SVM trained on tfidf of papers in your library, refreshed every day or so)' if g.user else 'You must be logged in and have some papers saved in your library.')
  return render_template('main.html', **ctx)

@app.route('/top', methods=['GET'])
def top():
  """ return top papers """
  ttstr = request.args.get('timefilter', 'week') # default is week
  vstr = request.args.get('vfilter', 'all') # default is all (no filter)
  legend = {'day':1, '3days':3, 'week':7, 'month':30, 'year':365, 'alltime':10000}
  tt = legend.get(ttstr, 7)
  curtime = int(time.time()) # in seconds
  papers = [p for p in TOP_SORTED_PAPERS if curtime - p['time_published'] < tt*24*60*60]
  papers = papers_filter_version(papers, vstr)
  ctx = default_context(papers, render_format='top',
                        msg='Top papers based on people\'s libraries:')
  return render_template('main.html', **ctx)

@app.route('/toptwtr', methods=['GET'])
def toptwtr():
  """ return top papers """
  papers = TWITTER_TOP
  ctx = default_context(papers, render_format='toptwtr',
                        msg='Top papers mentioned on Twitter over last 5 days:')
  return render_template('main.html', **ctx)

@app.route('/library')
def library():
  """ render user's library """
  papers = papers_from_library()
  ret = encode_json(papers, 500) # cap at 500 papers in someone's library. that's a lot!
  if g.user:
    msg = '%d papers in your library:' % (len(ret), )
  else:
    msg = 'You must be logged in. Once you are, you can save papers to your library (with the save icon on the right of each paper) and they will show up here.'
  ctx = default_context(papers, render_format='library', msg=msg)
  return render_template('main.html', **ctx)

@app.route('/libtoggle', methods=['POST'])
def review():
  """ user wants to toggle a paper in his library """
  
  # make sure user is logged in
  if not g.user:
    return 'NO' # fail... (not logged in). JS should prevent from us getting here.

  idvv = request.form['pid'] # includes version
  if not isvalidid(idvv):
    return 'NO' # fail, malformed id. weird.
  pid = strip_version(idvv)
  if not pid in db:
    return 'NO' # we don't know this paper. wat

  uid = session['user_id'] # id of logged in user

  # check this user already has this paper in library
  record = query_db('''select * from library where
          user_id = ? and paper_id = ?''', [uid, pid], one=True)
  print(record)

  ret = 'NO'
  if record:
    # record exists, erase it.
    g.db.execute('''delete from library where user_id = ? and paper_id = ?''', [uid, pid])
    g.db.commit()
    #print('removed %s for %s' % (pid, uid))
    ret = 'OFF'
  else:
    # record does not exist, add it.
    rawpid = strip_version(pid)
    g.db.execute('''insert into library (paper_id, user_id, update_time) values (?, ?, ?)''',
        [rawpid, uid, int(time.time())])
    g.db.commit()
    #print('added %s for %s' % (pid, uid))
    ret = 'ON'

  return ret

@app.route('/login', methods=['POST'])
def login():
  """ logs in the user. if the username doesn't exist creates the account """
  
  if not request.form['username']:
    flash('You have to enter a username')
  elif not request.form['password']:
    flash('You have to enter a password')
  elif get_user_id(request.form['username']) is not None:
    # username already exists, fetch all of its attributes
    user = query_db('''select * from user where
          username = ?''', [request.form['username']], one=True)
    if check_password_hash(user['pw_hash'], request.form['password']):
      # password is correct, log in the user
      session['user_id'] = get_user_id(request.form['username'])
      flash('User ' + request.form['username'] + ' logged in.')
    else:
      # incorrect password
      flash('User ' + request.form['username'] + ' already exists, wrong password.')
  else:
    # create account and log in
    creation_time = int(time.time())
    g.db.execute('''insert into user (username, pw_hash, creation_time) values (?, ?, ?)''',
      [request.form['username'], 
      generate_password_hash(request.form['password']), 
      creation_time])
    user_id = g.db.execute('select last_insert_rowid()').fetchall()[0][0]
    g.db.commit()

    session['user_id'] = user_id
    flash('New account %s created' % (request.form['username'], ))
  
  return redirect(url_for('intmain'))

@app.route('/logout')
def logout():
  session.pop('user_id', None)
  flash('You were logged out')
  return redirect(url_for('intmain'))

# -----------------------------------------------------------------------------
# int main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
   
  parser = argparse.ArgumentParser()
  parser.add_argument('-p', '--prod', dest='prod', action='store_true', help='run in prod?')
  parser.add_argument('-r', '--num_results', dest='num_results', type=int, default=200, help='number of results to return per query')
  parser.add_argument('--port', dest='port', type=int, default=5000, help='port to serve on')
  args = parser.parse_args()
  print(args)

  print('loading the paper database', Config.db_path)
  db = pickle.load(open(Config.db_path, 'rb'))
  
  print('loading tfidf_meta', Config.meta_path)
  meta = pickle.load(open(Config.meta_path, "rb"))
  vocab = meta['vocab']
  idf = meta['idf']

  print('loading paper similarities', Config.sim_path)
  sim_dict = pickle.load(open(Config.sim_path, "rb"))

  print('loading user recommendations', Config.user_sim_path)
  if os.path.isfile(Config.user_sim_path):
    user_sim = pickle.load(open(Config.user_sim_path, 'rb'))
  else:
    user_sim = {}

  print('loading twitter top', Config.tweet_path)
  if os.path.isfile(Config.tweet_path):
    TWITTER_TOP = pickle.load(open(Config.tweet_path, 'rb'))
    TWITTER_TOP = [db[pid] for count,pid in TWITTER_TOP]
  else:
    TWITTER_TOP = []

  print('precomputing papers date sorted...')
  DATE_SORTED_PAPERS = date_sort()

  if not os.path.isfile(Config.database_path):
    print('did not find as.db, trying to create an empty database from schema.sql...')
    print('this needs sqlite3 to be installed!')
    os.system('sqlite3 as.db < schema.sql')

  # compute top papers in peoples' libraries
  print('computing top papers...')
  def get_popular():
    sqldb = sqlite3.connect(Config.database_path)
    sqldb.row_factory = sqlite3.Row # to return dicts rather than tuples
    libs = sqldb.execute('''select * from library''').fetchall()
    counts = {}
    for lib in libs:
      pid = lib['paper_id']
      counts[pid] = counts.get(pid, 0) + 1
    return counts
  top_counts = get_popular()
  top_paper_counts = sorted([(v,k) for k,v in top_counts.items() if v > 0], reverse=True)
  print(top_paper_counts[:min(30, len(top_paper_counts))])
  TOP_SORTED_PAPERS = [db[q[1]] for q in top_paper_counts]

  # compute min and max time for all papers
  tts = [time.mktime(dateutil.parser.parse(p['updated']).timetuple()) for pid,p in db.items()]
  ttmin = min(tts)*1.0
  ttmax = max(tts)*1.0
  for pid,p in db.items():
    tt = time.mktime(dateutil.parser.parse(p['updated']).timetuple())
    p['tscore'] = (tt-ttmin)/(ttmax-ttmin)

  # some utilities for creating a search index for faster search
  punc = "'!\"#$%&\'()*+,./:;<=>?@[\\]^_`{|}~'" # removed hyphen from string.punctuation
  trans_table = {ord(c): None for c in punc}
  def makedict(s, forceidf=None, scale=1.0):
    words = set(s.lower().translate(trans_table).strip().split())
    out = {}
    for w in words: # todo: if we're using bigrams in vocab then this won't search over them
      if forceidf is None:
        if w in vocab:
          # we have idf for this
          idfval = idf[vocab[w]]*scale
        else:
          idfval = 1.0*scale # assume idf 1.0 (low)
      else:
        idfval = forceidf
      out[w] = idfval
    return out

  def merge_dicts(dlist):
    out = {}
    for d in dlist:
      for k,v in d.items():
        out[k] = out.get(k,0) + v
    return out

  # caching: check if db.p is younger than search_dict.p
  recompute_index = True
  if os.path.isfile(Config.search_dict_path):
    db_modified_time = os.path.getmtime(Config.db_path)
    search_modified_time = os.path.getmtime(Config.search_dict_path)
    if search_modified_time > db_modified_time:
      # search index exists and is more recent, no need
      recompute_index = False
  if recompute_index:
    print('building an index for faster search...')
    for pid in db:
      p = db[pid]
      dict_title = makedict(p['title'], forceidf=5, scale=3)
      dict_authors = makedict(' '.join(x['name'] for x in p['authors']), forceidf=5)
      dict_categories = {x['term'].lower():5 for x in p['tags']}
      if 'and' in dict_authors: 
        # special case for "and" handling in authors list
        del dict_authors['and']
      dict_summary = makedict(p['summary'])
      SEARCH_DICT[pid] = merge_dicts([dict_title, dict_authors, dict_categories, dict_summary])
    # and cache it in file
    print('writing ', Config.search_dict_path, ' as cache...')
    safe_pickle_dump(SEARCH_DICT, Config.search_dict_path)
  else:
    print('loading cached index for faster search from', Config.search_dict_path)
    SEARCH_DICT = pickle.load(open(Config.search_dict_path, 'rb'))

  # start
  if args.prod:
    # run on Tornado instead, since running raw Flask in prod is not recommended
    print('starting tornado!')
    from tornado.wsgi import WSGIContainer
    from tornado.httpserver import HTTPServer
    from tornado.ioloop import IOLoop
    from tornado.log import enable_pretty_logging
    enable_pretty_logging()
    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(args.port)
    IOLoop.instance().start()
  else:
    print('starting flask!')
    app.debug = True
    app.run(port=args.port)
