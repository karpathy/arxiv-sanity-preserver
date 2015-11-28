from flask import Flask
from flask import render_template
from flask import request
import cPickle as pickle
import numpy as np
import json

app = Flask(__name__)
app.debug = True

NRET = 25 # number of results to return

def papers_search(q):
  scores = []
  for pid in db:
    p = db[pid]
    score = 0
    # search titles
    if q in p['title']:
      score += 10.0
    # search authors
    score += sum(5.0 for x in p['authors'] if q in x['name'])
    # search abstracts
    score += 1.0 * p['summary'].count(q)
    scores.append((score, p))
  scores.sort(reverse=True) # descending
  out = [x[1] for x in scores if x[0] > 0]
  return out

def papers_similar(pid):
  ix = [i for i,p in enumerate(tfidf['pids']) if p == pid]
  if len(ix) == 1:
    ix0 = ix[0]
    xquery = X[ix0, :]
    ds = np.sum(np.square(X - xquery), axis=1)
    scores = [(-ds[i], tfidf['pids'][i]) for i in xrange(X.shape[0])]
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
    ret.append(struct)
  return ret

@app.route("/")
@app.route("/<request_pid>")
def intmain(request_pid=None):
  if request_pid == 'favicon.ico': return '' # must be better way, todo
  
  if request_pid is None:
    # ??? 
    q = 'RNN'
    papers = papers_search(q) # perform the query and get sorted documents
  else:
    papers = papers_similar(request_pid)

  ret = encode_json(papers, NRET) # encode the top few to json
  return render_template('main.html', papers=ret, numpapers=len(db))

@app.route("/search", methods=['GET'])
def search():
  q = request.args.get('q', '') # get the search request
  papers = papers_search(q) # perform the query and get sorted documents
  ret = encode_json(papers, NRET) # encode the top few to json
  return render_template('main.html', papers=ret, numpapers=len(db)) # weeee

if __name__ == "__main__":
  # load main database
  db = pickle.load(open('db.p', 'rb'))
  # load tfidf vectors
  tfidf = pickle.load(open("tfidf.p", "rb"))
  X = tfidf['X'].todense()
  app.run()
