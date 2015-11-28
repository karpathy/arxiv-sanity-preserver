import os
import feedparser
import cPickle as pickle

def encode(d):
  """ 
  get rid of feedparser bs with a deep copy. UNBELIEVABLE. I hate when libs 
  wrap simple things in their own classes.
  """
  if isinstance(d, feedparser.FeedParserDict) or isinstance(d, dict):
    j = {}
    for k in d.keys():
      j[k] = encode(d[k])
    return j
  elif isinstance(d, list):
    l = []
    for k in d:
      l.append(encode(k))
    return l
  else:
    return d

files = os.listdir('raw')
out = {}
for f in files:
  p = 'raw/' + f
  print 'reading ', p
  txt = open(p, 'r').read()
  parse = feedparser.parse(txt)
  for e in parse.entries:

    j = encode(e)

    s = j['id']
    ix = s.rfind('/')
    rawid = j['id'][ix+1:] # extract just the id (and the version)
    j['rawid'] = rawid
    out[rawid] = j

print 'read %d unique papers' % (len(out), )
pickle.dump(out, open( "db.p", "wb" ))


