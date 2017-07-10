import os
import json
import time
import pickle
import argparse
import datetime
import dateutil.parser
from random import shuffle, randrange, uniform

import numpy as np
from sqlite3 import dbapi2 as sqlite3
from hashlib import md5
from flask import Flask, request, session, url_for, redirect, \
     render_template, abort, g, flash, _app_ctx_stack
from flask_limiter import Limiter
from werkzeug import check_password_hash, generate_password_hash
import pymongo

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
    struct['rawpid'] = p['_rawid']
    struct['category'] = p['arxiv_primary_category']['term']
    struct['authors'] = [a['name'] for a in p['authors']]
    struct['link'] = p['link']
    struct['in_library'] = 1 if p['_rawid'] in libids else 0
    if send_abstracts:
      struct['abstract'] = p['summary']
    if send_images:
      struct['img'] = '/static/thumbs/' + idvv + '.pdf.jpg'
    struct['tags'] = [t['term'] for t in p['tags']]
    
    # render time information nicely
    timestruct = dateutil.parser.parse(p['updated'])
    struct['published_time'] = '%s/%s/%s' % (timestruct.month, timestruct.day, timestruct.year)
    timestruct = dateutil.parser.parse(p['published'])
    struct['originally_published_time'] = '%s/%s/%s' % (timestruct.month, timestruct.day, timestruct.year)

    # fetch amount of discussion on this paper
    struct['num_discussion'] = comments.count({ 'pid': p['_rawid'] })

    # arxiv comments from the authors (when they submit the paper)
    cc = p.get('arxiv_comment', '')
    if len(cc) > 100:
      cc = cc[:100] + '...' # crop very long comments
    struct['comment'] = cc

    ret.append(struct)
  return ret

# -----------------------------------------------------------------------------
# A class to store values for RSS feed
# -----------------------------------------------------------------------------

class RssValues(object):
  def __init__(self, title, link, summary):
    self.title = title
    self.link = link
    self.summary = summary
  def __repr__(self):
    return "%s at %s" % (self.title, self.link)

# -----------------------------------------------------------------------------
# flask request handling
# -----------------------------------------------------------------------------
@app.route("/recent_rss.xml")
def recent_rss():
  vstr = request.args.get('vfilter', 'all')
  papers = [db[pid] for pid in DATE_SORTED_PIDS]  # precomputed
  papers = papers_filter_version(papers, vstr)
  render_paper = []
  for paper in papers:
    if 'updated' in paper:
      updated_dt = datetime.datetime.strptime(paper['updated'], "%Y-%m-%dT%H:%M:%SZ")
      yesterday_dt = datetime.datetime.today() - datetime.timedelta(days=1)
      if updated_dt > yesterday_dt:
        continue
    summary = ''
    title = ''
    link = ''
    if 'link' in paper:
      link = paper['link']
    else:
      continue  # if link does not exist, do not add to list
    if 'summary' in paper:
      summary = paper['summary']
    if 'title' in paper:
      title = paper['title']
    render_paper.append(RssValues(title, link, summary))
  print("render_paper=", render_paper)
  return render_template('rss.xml', papers=render_paper)

def default_context(papers, **kws):
  top_papers = encode_json(papers, args.num_results)

  # prompt logic
  show_prompt = 'no'
  try:
    if Config.beg_for_hosting_money and g.user and uniform(0,1) < 0.05:
      uid = session['user_id']
      entry = goaway_collection.find_one({ 'uid':uid })
      if not entry:
        lib_count = query_db('''select count(*) from library where user_id = ?''', [uid], one=True)
        lib_count = lib_count['count(*)']
        if lib_count > 0: # user has some items in their library too
          show_prompt = 'yes'
  except Exception as e:
    print(e)

  ans = dict(papers=top_papers, numresults=len(papers), totpapers=len(db), tweets=[], msg='', show_prompt=show_prompt, pid_to_users={})
  ans.update(kws)
  return ans

@app.route('/goaway', methods=['POST'])
def goaway():
  if not g.user: return # weird
  uid = session['user_id']
  entry = goaway_collection.find_one({ 'uid':uid })
  if not entry: # ok record this user wanting it to stop
    username = get_username(session['user_id'])
    print('adding', uid, username, 'to goaway.')
    goaway_collection.insert_one({ 'uid':uid, 'time':int(time.time()) })
  return 'OK'

@app.route("/")
def intmain():
  vstr = request.args.get('vfilter', 'all')
  papers = [db[pid] for pid in DATE_SORTED_PIDS] # precomputed
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

@app.route('/discuss', methods=['GET'])
def discuss():
  """ return discussion related to a paper """
  pid = request.args.get('id', '') # paper id of paper we wish to discuss
  papers = [db[pid]] if pid in db else []

  # fetch the comments
  comms_cursor = comments.find({ 'pid':pid }).sort([('time_posted', pymongo.DESCENDING)])
  comms = list(comms_cursor)
  for c in comms:
    c['_id'] = str(c['_id']) # have to convert these to strs from ObjectId, and backwards later http://api.mongodb.com/python/current/tutorial.html

  # fetch the counts for all tags
  tag_counts = []
  for c in comms:
    cc = [tags_collection.count({ 'comment_id':c['_id'], 'tag_name':t }) for t in TAGS]
    tag_counts.append(cc);

  # and render
  ctx = default_context(papers, render_format='default', comments=comms, gpid=pid, tags=TAGS, tag_counts=tag_counts)
  return render_template('discuss.html', **ctx)

@app.route('/comment', methods=['POST'])
def comment():
  """ user wants to post a comment """
  anon = int(request.form['anon'])

  if g.user and (not anon):
    username = get_username(session['user_id'])
  else:
    # generate a unique username if user wants to be anon, or user not logged in.
    username = 'anon-%s-%s' % (str(int(time.time())), str(randrange(1000)))

  # process the raw pid and validate it, etc
  try:
    pid = request.form['pid']
    if not pid in db: raise Exception("invalid pid")
    version = db[pid]['_version'] # most recent version of this paper
  except Exception as e:
    print(e)
    return 'bad pid. This is most likely Andrej\'s fault.'

  # create the entry
  entry = {
    'user': username,
    'pid': pid, # raw pid with no version, for search convenience
    'version': version, # version as int, again as convenience
    'conf': request.form['conf'],
    'anon': anon,
    'time_posted': time.time(),
    'text': request.form['text'],
  }

  # enter into database
  print(entry)
  comments.insert_one(entry)
  return 'OK'

@app.route("/discussions", methods=['GET'])
def discussions():
  # return most recently discussed papers
  comms_cursor = comments.find().sort([('time_posted', pymongo.DESCENDING)]).limit(100)

  # get the (unique) set of papers.
  papers = []
  have = set()
  for e in comms_cursor:
    pid = e['pid']
    if pid in db and not pid in have:
      have.add(pid)
      papers.append(db[pid])

  ctx = default_context(papers, render_format="discussions")
  return render_template('main.html', **ctx)

@app.route('/toggletag', methods=['POST'])
def toggletag():

  if not g.user: 
    return 'You have to be logged in to tag. Sorry - otherwise things could get out of hand FAST.'

  # get the tag and validate it as an allowed tag
  tag_name = request.form['tag_name']
  if not tag_name in TAGS:
    print('tag name %s is not in allowed tags.' % (tag_name, ))
    return "Bad tag name. This is most likely Andrej's fault."

  pid = request.form['pid']
  comment_id = request.form['comment_id']
  username = get_username(session['user_id'])
  time_toggled = time.time()
  entry = {
    'username': username,
    'pid': pid,
    'comment_id': comment_id,
    'tag_name': tag_name,
    'time': time_toggled,
  }

  # remove any existing entries for this user/comment/tag
  result = tags_collection.delete_one({ 'username':username, 'comment_id':comment_id, 'tag_name':tag_name })
  if result.deleted_count > 0:
    print('cleared an existing entry from database')
  else:
    print('no entry existed, so this is a toggle ON. inserting:')
    print(entry)
    tags_collection.insert_one(entry)

  return 'OK'

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
  top_sorted_papers = [db[p] for p in TOP_SORTED_PIDS]
  papers = [p for p in top_sorted_papers if curtime - p['time_published'] < tt*24*60*60]
  papers = papers_filter_version(papers, vstr)
  ctx = default_context(papers, render_format='top',
                        msg='Top papers based on people\'s libraries:')
  return render_template('main.html', **ctx)

@app.route('/toptwtr', methods=['GET'])
def toptwtr():
  """ return top papers """
  ttstr = request.args.get('timefilter', 'day') # default is day
  tweets_top = {'day':tweets_top1, 'week':tweets_top7, 'month':tweets_top30}[ttstr]
  cursor = tweets_top.find().sort([('vote', pymongo.DESCENDING)]).limit(100)
  papers, tweets = [], []
  for rec in cursor:
    if rec['pid'] in db:
      papers.append(db[rec['pid']])
      tweet = {k:v for k,v in rec.items() if k != '_id'}
      tweets.append(tweet)
  ctx = default_context(papers, render_format='toptwtr', tweets=tweets,
                        msg='Top papers mentioned on Twitter over last ' + ttstr + ':')
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

@app.route('/friends', methods=['GET'])
def friends():
    
    ttstr = request.args.get('timefilter', 'week') # default is week
    legend = {'day':1, '3days':3, 'week':7, 'month':30, 'year':365}
    tt = legend.get(ttstr, 7)

    papers = []
    pid_to_users = {}
    if g.user:
        # gather all the people we are following
        username = get_username(session['user_id'])
        edges = list(follow_collection.find({ 'who':username }))
        # fetch all papers in all of their libraries, and count the top ones
        counts = {}
        for edict in edges:
            whom = edict['whom']
            uid = get_user_id(whom)
            user_library = query_db('''select * from library where user_id = ?''', [uid])
            libids = [strip_version(x['paper_id']) for x in user_library]
            for lid in libids:
                if not lid in counts:
                    counts[lid] = []
                counts[lid].append(whom)

        keys = list(counts.keys())
        keys.sort(key=lambda k: len(counts[k]), reverse=True) # descending by count
        papers = [db[x] for x in keys]
        # finally filter by date
        curtime = int(time.time()) # in seconds
        papers = [x for x in papers if curtime - x['time_published'] < tt*24*60*60]
        # trim at like 100
        if len(papers) > 100: papers = papers[:100]
        # trim counts as well correspondingly
        pid_to_users = { p['_rawid'] : counts.get(p['_rawid'], []) for p in papers }

    if not g.user:
        msg = "You must be logged in and follow some people to enjoy this tab."
    else:
        if len(papers) == 0:
            msg = "No friend papers present. Try to extend the time range, or add friends by clicking on your account name (top, right)"
        else:
            msg = "Papers in your friend's libraries:"

    ctx = default_context(papers, render_format='friends', pid_to_users=pid_to_users, msg=msg)
    return render_template('main.html', **ctx)

@app.route('/account')
def account():
    ctx = { 'totpapers':len(db) }

    followers = []
    following = []
    # fetch all followers/following of the logged in user
    if g.user:
        username = get_username(session['user_id'])
        
        following_db = list(follow_collection.find({ 'who':username }))
        for e in following_db:
            following.append({ 'user':e['whom'], 'active':e['active'] })

        followers_db = list(follow_collection.find({ 'whom':username }))
        for e in followers_db:
            followers.append({ 'user':e['who'], 'active':e['active'] })

    ctx['followers'] = followers
    ctx['following'] = following
    return render_template('account.html', **ctx)

@app.route('/requestfollow', methods=['POST'])
def requestfollow():
    if request.form['newf'] and g.user:
        # add an entry: this user is requesting to follow a second user
        who = get_username(session['user_id'])
        whom = request.form['newf']
        # make sure whom exists in our database
        whom_id = get_user_id(whom)
        if whom_id is not None:
            e = { 'who':who, 'whom':whom, 'active':0, 'time_request':int(time.time()) }
            print('adding request follow:')
            print(e)
            follow_collection.insert_one(e)

    return redirect(url_for('account'))

@app.route('/removefollow', methods=['POST'])
def removefollow():
    user = request.form['user']
    lst = request.form['lst']
    if user and lst:
        username = get_username(session['user_id'])
        if lst == 'followers':
            # user clicked "X" in their followers list. Erase the follower of this user
            who = user
            whom = username
        elif lst == 'following':
            # user clicked "X" in their following list. Stop following this user.
            who = username
            whom = user
        else:
            return 'NOTOK'

        delq = { 'who':who, 'whom':whom }
        print('deleting from follow collection:', delq)
        follow_collection.delete_one(delq)
        return 'OK'
    else:
        return 'NOTOK'

@app.route('/addfollow', methods=['POST'])
def addfollow():
    user = request.form['user']
    lst = request.form['lst']
    if user and lst:
        username = get_username(session['user_id'])
        if lst == 'followers':
            # user clicked "OK" in the followers list, wants to approve some follower. make active.
            who = user
            whom = username
            delq = { 'who':who, 'whom':whom }
            print('making active in follow collection:', delq)
            follow_collection.update_one(delq, {'$set':{'active':1}})
            return 'OK'
        
    return 'NOTOK'

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

  if not os.path.isfile(Config.database_path):
    print('did not find as.db, trying to create an empty database from schema.sql...')
    print('this needs sqlite3 to be installed!')
    os.system('sqlite3 as.db < schema.sql')

  print('loading the paper database', Config.db_serve_path)
  db = pickle.load(open(Config.db_serve_path, 'rb'))
  
  print('loading tfidf_meta', Config.meta_path)
  meta = pickle.load(open(Config.meta_path, "rb"))
  vocab = meta['vocab']
  idf = meta['idf']

  print('loading paper similarities', Config.sim_path)
  sim_dict = pickle.load(open(Config.sim_path, "rb"))

  print('loading user recommendations', Config.user_sim_path)
  user_sim = {}
  if os.path.isfile(Config.user_sim_path):
    user_sim = pickle.load(open(Config.user_sim_path, 'rb'))
  
  print('loading serve cache...', Config.serve_cache_path)
  cache = pickle.load(open(Config.serve_cache_path, "rb"))
  DATE_SORTED_PIDS = cache['date_sorted_pids']
  TOP_SORTED_PIDS = cache['top_sorted_pids']
  SEARCH_DICT = cache['search_dict']

  print('connecting to mongodb...')
  client = pymongo.MongoClient()
  mdb = client.arxiv
  tweets_top1 = mdb.tweets_top1
  tweets_top7 = mdb.tweets_top7
  tweets_top30 = mdb.tweets_top30
  comments = mdb.comments
  tags_collection = mdb.tags
  goaway_collection = mdb.goaway
  follow_collection = mdb.follow
  print('mongodb tweets_top1 collection size:', tweets_top1.count())
  print('mongodb tweets_top7 collection size:', tweets_top7.count())
  print('mongodb tweets_top30 collection size:', tweets_top30.count())
  print('mongodb comments collection size:', comments.count())
  print('mongodb tags collection size:', tags_collection.count())
  print('mongodb goaway collection size:', goaway_collection.count())
  print('mongodb follow collection size:', follow_collection.count())
  
  TAGS = ['insightful!', 'thank you', 'agree', 'disagree', 'not constructive', 'troll', 'spam']

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
    app.debug = False
    app.run(port=args.port, host='0.0.0.0')
