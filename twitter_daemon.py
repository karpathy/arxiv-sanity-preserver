import re
import pytz
import time
import pickle
import datetime

from dateutil import parser
import twitter # pip install python-twitter

from utils import Config, safe_pickle_dump

sleep_time = 60*10 # in seconds
max_days_keep = 5 # max number of days to keep a tweet in memory

def get_db_pids():
  print('loading the paper database', Config.db_path)
  db = pickle.load(open(Config.db_path, 'rb'))
  # I know this looks weird, but I don't trust dict_keys to be efficient with "in" operator. 
  # I also don't trust it to keep some reference to the whole dict, as I'm hoping db here deallocates.
  # Can't find good docs here
  pid_dict = {p:1 for p in db} 
  return pid_dict

def get_keys():
  lines = open('twitter.txt', 'r').read().splitlines()
  return lines

# authenticate
keys = get_keys()
api = twitter.Api(consumer_key=keys[0],
                  consumer_secret=keys[1],
                  access_token_key=keys[2],
                  access_token_secret=keys[3])
print(api.VerifyCredentials())

def extract_arxiv_pids(r):
  pids = []
  for u in r.urls:
    m = re.search('arxiv.org/abs/(.+)', u.expanded_url)
    if m: 
      rawid = m.group(1)
      pids.append(rawid)
  return pids

db_pids = get_db_pids()
seen = {}
epochd = datetime.datetime(1970,1,1,tzinfo=pytz.utc) # time of epoch
while True:

  try:
    results = api.GetSearch(raw_query="q=arxiv.org&result_type=recent&count=100")
    ok = True
  except Exception as e:
    print('there was some problem:')
    print(e)
    time.sleep(sleep_time)
    continue

  tnow = time.time()
  num_processed = 0
  parsed = []
  for r in results:
    arxiv_pids = extract_arxiv_pids(r)
    arxiv_pids = [p for p in arxiv_pids if p in db_pids] # filter to those that are in our paper db
    if not arxiv_pids: continue # nothing relevant here, lets move on
    if r.id in seen: continue # skip, already saw and recorded
    seen[r.id] = {'seen':tnow} # mark as seen at this time
    num_processed += 1

    # collect all arxiv paper ids from valid urls
    seen[r.id]['pids'] = arxiv_pids

    # parse & records time of this tweet
    d = parser.parse(r.created_at)
    time_posted = (d - epochd).total_seconds()
    seen[r.id]['time_posted'] = time_posted
    
  print('processed %d/%d new tweets. Currently maintaining total %d' % (num_processed, len(results), len(seen)))

  # maintain state: if something was seen > few days ago, forget it
  maxdt = 60*60*24*max_days_keep
  seen_new = { tweetid:d for tweetid,d in seen.items() if tnow - d['time_posted'] < maxdt }
  print('previous seen dict had %d tweets, pruning to %d' % (len(seen), len(seen_new)))
  seen = seen_new # swap

  # compile all votes and write output for serving
  votes = {}
  for tweetid,d in seen.items():
    for pid in d['pids']:
      votes[pid] = votes.get(pid, 0) + 1
  votes = [(v,k) for k,v in votes.items()]
  votes.sort(reverse=True, key=lambda x: x[0]) # descending
  print('top votes', votes[:min(len(votes), 10)])
  print('writing', Config.tweet_path)
  safe_pickle_dump(votes, Config.tweet_path)
  
  # and sleep for a while
  print('sleeping', sleep_time)
  time.sleep(sleep_time)

