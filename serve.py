from sqlite3 import dbapi2 as sqlite3
from hashlib import md5
from flask import Flask, request, session, url_for, redirect, \
     render_template, abort, g, flash, _app_ctx_stack
from werkzeug import check_password_hash, generate_password_hash
import cPickle as pickle
import numpy as np
import json
import time
import dateutil.parser
import argparse
from random import shuffle
import re
import os

# configuration
DATABASE = 'as.db'
if os.path.isfile('secret_key.txt'):
  SECRET_KEY = open('secret_key.txt', 'r').read()
else:
  SECRET_KEY = 'devkey, should be in a file'
app = Flask(__name__)
app.config.from_object(__name__)

SEARCH_DICT = {}

# -----------------------------------------------------------------------------
# utilities for database interactions 
# -----------------------------------------------------------------------------
# to initialize the database: sqlite3 as.db < schema.sql

def connect_db():
  sqlite_db = sqlite3.connect(DATABASE)
  sqlite_db.row_factory = sqlite3.Row # to return dicts rather than tuples
  return sqlite_db

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
# search/sort functionality
# -----------------------------------------------------------------------------
def papers_shuffle():
  ks = db.keys()
  shuffle(ks)
  return [db[k] for k in ks]

def date_sort():
  scores = []
  for pid in db:
    p = db[pid]
    timestruct = dateutil.parser.parse(p['updated'])
    scores.append((timestruct, p))
  scores.sort(reverse=True)
  out = [sp[1] for sp in scores]
  return out

def papers_search_old(qraw):
  """ deprecated, slow, brute-force search """
  qparts = qraw.lower().strip().split() # split by spaces

  # brute force search with unigrams, weeee
  scores = []
  for pid in db:
    p = db[pid]
    score = 0
    for q in qparts:
      # search titles
      if q in p['title'].lower():
        score += 5.0
      # search authors
      score += sum(3.0 for x in p['authors'] if q in x['name'].lower())
      # search abstracts
      score += min(3.0, 1.0 * p['summary'].lower().count(q)) # robustify with min
    scores.append((score, p))
  scores.sort(reverse=True) # descending
  out = [x[1] for x in scores if x[0] > 0]
  return out

def papers_search(qraw):
  qparts = qraw.lower().strip().split() # split by spaces
  # use reverse index and accumulate scores
  scores = []
  for pid in db:
    p = db[pid]
    score = sum(SEARCH_DICT[pid].get(q,0) for q in qparts)
    scores.append((score, p))
  scores.sort(reverse=True) # descending
  out = [x[1] for x in scores if x[0] > 0]
  return out

def strip_version(idstr):
  parts = idstr.split('v')
  return parts[0]

def papers_similar(pid):
  if pid in tfidf['ptoi']:
    ix0 = tfidf['ptoi'][pid]
    xquery = X[ix0, np.newaxis]
    ds = np.asarray(np.dot(X, xquery.T)).ravel() # L2 normalized tfidf vectors
    scores = [(ds[i], tfidf['pids'][i]) for i in xrange(X.shape[0])]
    scores.sort(reverse=True) # descending
    out = [db[strip_version(sp[1])] for sp in scores]
    return out
  else:
    return [db[pid]] # err wat?

def encode_json(ps, n=10, send_images=True, send_abstracts=True):

  ret = []
  for i in xrange(min(len(ps),n)):
    p = ps[i]
    idvv = '%sv%d' % (p['_rawid'], p['_version'])

    struct = {}
    struct['title'] = p['title']
    struct['pid'] = idvv
    struct['authors'] = [a['name'] for a in p['authors']]
    struct['link'] = p['link']
    if send_abstracts:
      struct['abstract'] = p['summary']
    if send_images:
      struct['img'] = '/static/thumbs/' + idvv + '.pdf.jpg'
    struct['tags'] = [t['term'] for t in p['tags']]
    
    timestruct = dateutil.parser.parse(p['updated'])
    struct['published_time'] = '%s/%s/%s' % (timestruct.month, timestruct.day, timestruct.year)

    cc = p.get('arxiv_comment', '')
    if len(cc) > 100:
      cc = cc[:100] + '...' # crop very long comments
    struct['comment'] = cc

    # also fetch reviews for the paper
    reviews = query_db('''select * from review where paper_id = ?''', [idvv])
    processed_reviews = []
    for r in reviews:
      rr = {}
      rr['text'] = r['text']
      rr['username'] = get_username(r['author_id'])
      rr['created'] = time.ctime(r['creation_time'])
      processed_reviews.append(rr)
    struct['reviews'] = processed_reviews

    ret.append(struct)
  return ret

# -----------------------------------------------------------------------------
# flask request handling
# -----------------------------------------------------------------------------

# "1511.08198v1" is an example of a valid arxiv id that we accept
def isvalidid(pid):
  return re.match('^\d+\.\d+(v\d+)?$', pid)

@app.route("/")
@app.route("/<request_pid>")
def intmain(request_pid=None):

  if request_pid is None:
    #papers = papers_shuffle() # perform the query and get sorted documents
    papers = date_sort()
    ret = encode_json(papers, 20)
    msg = 'Showing 20 most recent Arxiv papers:'
  else:
    if not isvalidid(request_pid):
      return '' # these are requests for icons, things like robots.txt, etc

    papers = papers_similar(request_pid)
    ret = encode_json(papers, args.num_results) # encode the top few to json
    msg = ''
  return render_template('main.html', papers=ret, numpapers=len(db), msg=msg)

@app.route("/search", methods=['GET'])
def search():
  q = request.args.get('q', '') # get the search request
  papers = papers_search(q) # perform the query and get sorted documents
  ret = encode_json(papers, args.num_results) # encode the top few to json
  return render_template('main.html', papers=ret, numpapers=len(db), msg='') # weeee

@app.route('/review', methods=['POST'])
def review():
  """ when user wants to add a review """
  
  # make sure user is logged in
  if not g.user:
    flash('the user must be logged in to review.')
    return redirect(url_for('intmain'))

  pid = request.form['pid'] # includes version
  if not isvalidid(pid):
    flash('malformed arxiv paper id')
    return redirect(url_for('intmain'))

  txt = request.form['reviewtext']
  creation_time = int(time.time())
  pidraw = pid.split('v')[0] # part without the v
  g.db.execute('''insert into review (paper_id_raw, paper_id, author_id, text, creation_time, update_time) values (?, ?, ?, ?, ?, ?)''',
      [pidraw, pid, session['user_id'], txt, creation_time, creation_time])
  g.db.commit()

  flash('review added.')
  return redirect(url_for('intmain'))

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
  parser.add_argument('-r', '--num_results', dest='num_results', type=int, default=20, help='number of results to return per query')
  parser.add_argument('--port', dest='port', type=int, default=5000, help='port to serve on')
  args = parser.parse_args()
  print args

  print 'loading db.p...'
  db = pickle.load(open('db.p', 'rb'))
  
  print 'loading tfidf.p...'
  tfidf = pickle.load(open("tfidf.p", "rb"))
  X = tfidf['X'].todense()
  vocab = tfidf['vocab']
  idf = tfidf['idf']

  # some utilities for creating a search index for faster search
  punc = "'!\"#$%&\'()*+,./:;<=>?@[\\]^_`{|}~'" # removed hyphen from string.punctuation
  trans_table = {ord(c): None for c in punc}
  def makedict(s, forceidf=None):
    words = s.lower().translate(trans_table).strip().split()
    out = {}
    for w in words: # todo: if we're using bigrams in vocab then this won't search over them
      if forceidf is None:
        if w in vocab:
          # we have idf for this
          idfval = idf[vocab[w]]
        else:
          idfval = 1.0 # assume idf 1.0 (low)
      else:
        idfval = forceidf
      out[w] = idfval # note, we're overwriting, so no adding up
    return out

  def merge_dicts(dlist):
    out = {}
    for d in dlist:
      for k,v in d.iteritems():
        out[k] = out.get(k,0) + v
    return out

  # caching: check if db.p is younger than search_dict.p
  recompute_index = True
  if os.path.isfile('search_dict.p'):
    db_modified_time = os.path.getmtime('db.p')
    search_modified_time = os.path.getmtime('search_dict.p')
    if search_modified_time > db_modified_time:
      # search index exists and is more recent, no need
      recompute_index = False
  if recompute_index:
    print 'building an index for faster search...'
    for pid in db:
      p = db[pid]
      dict_title = makedict(p['title'])
      dict_authors = makedict(' '.join(x['name'] for x in p['authors']), 10.0)
      dict_summary = makedict(p['summary'])
      SEARCH_DICT[pid] = merge_dicts([dict_title, dict_authors, dict_summary])
    # and cache it in file
    print 'writing search_dict.p as cache'
    pickle.dump(SEARCH_DICT, open('search_dict.p', 'wb'))
  else:
    print 'loading cached index for faster search...'
    SEARCH_DICT = pickle.load(open('search_dict.p', 'rb'))

  # start
  if args.prod:
    # run on Tornado instead, since running raw Flask in prod is not recommended
    print 'starting tornado!'
    from tornado.wsgi import WSGIContainer
    from tornado.httpserver import HTTPServer
    from tornado.ioloop import IOLoop
    from tornado.log import enable_pretty_logging
    enable_pretty_logging()
    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(args.port)
    IOLoop.instance().start()
    #app.run(host='0.0.0.0', threaded=True)
  else:
    print 'starting flask!'
    app.debug = True
    app.run(port=args.port)
