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

def papers_search(qraw):
  qparts = qraw.lower().split() # split by spaces

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
      score += min(2.0, 1.0 * p['summary'].lower().count(q)) # robustify with min
    scores.append((score, p))
  scores.sort(reverse=True) # descending
  out = [x[1] for x in scores if x[0] > 0]
  return out

def papers_similar(pid):
  ix = [i for i,p in enumerate(tfidf['pids']) if p == pid]
  if len(ix) == 1:
    ix0 = ix[0]
    xquery = X[ix0, np.newaxis]
    ds = np.asarray(np.dot(X, xquery.T)).ravel() # L2 normalized tfidf vectors
    scores = [(ds[i], tfidf['pids'][i]) for i in xrange(X.shape[0])]
    scores.sort(reverse=True) # descending
    out = [db[sp[1]] for sp in scores]
    return out
  else:
    return [db[pid]] # err wat?

def encode_json(ps, n=10):

  ret = []
  for i in xrange(min(len(ps),n)):
    p = ps[i]
    struct = {}
    struct['title'] = p['title']
    struct['pid'] = p['rawid']
    struct['authors'] = [a['name'] for a in p['authors']]
    struct['link'] = p['link']
    struct['abstract'] = p['summary']
    struct['img'] = '/static/thumbs/' + p['rawid'] + '.pdf.jpg'
    struct['tags'] = [t['term'] for t in p['tags']]
    
    timestruct = dateutil.parser.parse(p['updated'])
    struct['published_time'] = '%s/%s/%s' % (timestruct.month, timestruct.day, timestruct.year)

    cc = p.get('arxiv_comment', '')
    if len(cc) > 100:
      cc = cc[:100] + '...'
    struct['comment'] = cc

    ret.append(struct)
  return ret

@app.route("/")
@app.route("/<request_pid>")
def intmain(request_pid=None):
  if request_pid == 'favicon.ico': return '' # must be better way, todo
  
  if request_pid is None:
    papers = papers_shuffle() # perform the query and get sorted documents
  else:
    papers = papers_similar(request_pid)

  ret = encode_json(papers, args.num_results) # encode the top few to json
  return render_template('main.html', papers=ret, numpapers=len(db))

@app.route("/search", methods=['GET'])
def search():
  q = request.args.get('q', '') # get the search request
  papers = papers_search(q) # perform the query and get sorted documents
  ret = encode_json(papers, args.num_results) # encode the top few to json
  return render_template('main.html', papers=ret, numpapers=len(db)) # weeee

if __name__ == "__main__":
   
  parser = argparse.ArgumentParser()
  parser.add_argument('-p', '--prod', dest='prod', action='store_true', help='run in prod?')
  parser.add_argument('-r', '--num_results', dest='num_results', type=int, default=25, help='number of results to return per query')
  args = parser.parse_args()
  print args

  # load main database
  db = pickle.load(open('db.p', 'rb'))
  # load tfidf vectors
  tfidf = pickle.load(open("tfidf.p", "rb"))
  X = tfidf['X'].todense()

  if args.prod:
    app.run(host='0.0.0.0')
  else:
    app.debug = True
    app.run()
