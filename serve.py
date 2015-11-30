from flask import Flask
from flask import render_template
from flask import request
import cPickle as pickle
import numpy as np
import json
import time
import dateutil.parser
import argparse
from random import shuffle

app = Flask(__name__)

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
    score = sum(p['search_dict'].get(q,0) for q in qparts)
    scores.append((score, p))
  scores.sort(reverse=True) # descending
  out = [x[1] for x in scores if x[0] > 0]
  return out

def papers_similar(pid):
  if pid in tfidf['ptoi']:
    ix0 = tfidf['ptoi'][pid]
    xquery = X[ix0, np.newaxis]
    ds = np.asarray(np.dot(X, xquery.T)).ravel() # L2 normalized tfidf vectors
    scores = [(ds[i], tfidf['pids'][i]) for i in xrange(X.shape[0])]
    scores.sort(reverse=True) # descending
    out = [db[sp[1]] for sp in scores]
    return out
  else:
    return [db[pid]] # err wat?

def encode_json(ps, n=10, send_images=True, send_abstracts=True):

  ret = []
  for i in xrange(min(len(ps),n)):
    p = ps[i]
    struct = {}
    struct['title'] = p['title']
    struct['pid'] = p['rawid']
    struct['authors'] = [a['name'] for a in p['authors']]
    struct['link'] = p['link']
    if send_abstracts:
      struct['abstract'] = p['summary']
    if send_images:
      struct['img'] = '/static/thumbs/' + p['rawid'] + '.pdf.jpg'
    struct['tags'] = [t['term'] for t in p['tags']]
    
    timestruct = dateutil.parser.parse(p['updated'])
    struct['published_time'] = '%s/%s/%s' % (timestruct.month, timestruct.day, timestruct.year)

    cc = p.get('arxiv_comment', '')
    if len(cc) > 100:
      cc = cc[:100] + '...' # crop very long comments
    struct['comment'] = cc

    ret.append(struct)
  return ret

@app.route("/")
@app.route("/<request_pid>")
def intmain(request_pid=None):
  if request_pid == 'favicon.ico': return '' # must be better way, todo
  if request_pid == 'robots.txt': return '' # must be better way, todo

  if request_pid is None:
    #papers = papers_shuffle() # perform the query and get sorted documents
    papers = date_sort()
    ret = encode_json(papers, 100, send_images=False, send_abstracts=False)
    collapsed = 1
  else:
    papers = papers_similar(request_pid)
    ret = encode_json(papers, args.num_results) # encode the top few to json
    collapsed = 0
  return render_template('main.html', papers=ret, numpapers=len(db), collapsed=collapsed)

@app.route("/search", methods=['GET'])
def search():
  q = request.args.get('q', '') # get the search request
  papers = papers_search(q) # perform the query and get sorted documents
  ret = encode_json(papers, args.num_results) # encode the top few to json
  return render_template('main.html', papers=ret, numpapers=len(db), collapsed=0) # weeee

if __name__ == "__main__":
   
  parser = argparse.ArgumentParser()
  parser.add_argument('-p', '--prod', dest='prod', action='store_true', help='run in prod?')
  parser.add_argument('-r', '--num_results', dest='num_results', type=int, default=20, help='number of results to return per query')
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
    for w in words:
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

  print 'building an index for faster search...'
  for pid in db:
    p = db[pid]
    dict_title = makedict(p['title'])
    dict_authors = makedict(' '.join(x['name'] for x in p['authors']), 10.0)
    dict_summary = makedict(p['summary'])
    p['search_dict'] = merge_dicts([dict_title, dict_authors, dict_summary])

  #import code; code.interact(local=locals())
  print 'starting!'
  if args.prod:
    app.run(host='0.0.0.0')
  else:
    app.debug = True
    app.run()
