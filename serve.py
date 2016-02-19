from flask import Flask, render_template, request
import cPickle as pickle
import numpy as np
import json
import time
import dateutil.parser
import argparse
from random import shuffle
import re
import os

app = Flask(__name__)

SEARCH_DICT = {}

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

def papers_search(qraw):
  qparts = qraw.lower().strip().split() # split by spaces
  # use reverse index and accumulate scores
  scores = []
  for pid in db:
    p = db[pid]
    score = sum(SEARCH_DICT[pid].get(q,0) for q in qparts)
    # give a small boost to more recent papers
    score += 0.0001*p['tscore']
    scores.append((score, p))
  scores.sort(reverse=True) # descending
  out = [x[1] for x in scores if x[0] > 0]
  return out

def strip_version(idstr):
  """ identity function if arxiv id has no version, otherwise strips it. """
  parts = idstr.split('v')
  return parts[0]

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
    ks = sim_dict.keys()
    kok = [k for k in sim_dict.iterkeys() if rawpid in k]
    if kok:
      # ok we have at least one different version of this paper, lets use it instead
      id_use_instead = kok[0]
      return [db[strip_version(k)] for k in sim_dict[id_use_instead]]
    else:
      # return just the paper. we dont have similarities for it for some reason
      return [db[rawpid]]

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
    papers = DATE_SORTED_PAPERS # precomputed
    ret = encode_json(papers, 20)
    msg = 'Showing 20 most recent Arxiv papers:'
    render_format = 'recent'
  else:
    if not isvalidid(request_pid):
      return '' # these are requests for icons, things like robots.txt, etc
    papers = papers_similar(request_pid)
    ret = encode_json(papers, args.num_results) # encode the top few to json
    msg = ''
    render_format = 'paper'

  return render_template('main.html', papers=ret, numpapers=len(db), msg=msg, render_format=render_format)

@app.route("/search", methods=['GET'])
def search():
  q = request.args.get('q', '') # get the search request
  papers = papers_search(q) # perform the query and get sorted documents
  ret = encode_json(papers, args.num_results) # encode the top few to json
  return render_template('main.html', papers=ret, numpapers=len(db), msg='', render_format="search") # weeee

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
  
  print 'loading tfidf_meta.p...'
  meta = pickle.load(open("tfidf_meta.p", "rb"))
  vocab = meta['vocab']
  idf = meta['idf']

  print 'loading sim_dict.p...'
  sim_dict = pickle.load(open("sim_dict.p", "rb"))

  print 'precomputing papers date sorted...'
  DATE_SORTED_PAPERS = date_sort()

  # compute min and max time for all papers
  tts = [time.mktime(dateutil.parser.parse(p['updated']).timetuple()) for pid,p in db.iteritems()]
  ttmin = min(tts)*1.0
  ttmax = max(tts)*1.0
  for pid,p in db.iteritems():
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
      dict_title = makedict(p['title'], forceidf=5, scale=3)
      dict_authors = makedict(' '.join(x['name'] for x in p['authors']), forceidf=5)
      if 'and' in dict_authors: 
        # special case for "and" handling in authors list
        del dict_authors['and']
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
