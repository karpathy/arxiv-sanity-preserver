import os
import glob
import time
import pickle
import shutil
import random
from  urllib.request import urlopen

from utils import Config,dir_basename_from_pid

timeout_secs = 10 # after this many seconds we give up on a paper
if not os.path.exists(Config.pdf_dir): os.makedirs(Config.pdf_dir)
if not os.path.exists(Config.txt_dir): os.makedirs(Config.txt_dir)
print('Config.txt_dir',Config.txt_dir)
print('Config.pdf_dir',Config.pdf_dir)
have_pdf = set(f for f in glob.glob(Config.pdf_dir + "**/**/*.pdf", recursive=True) ) # get list of all pdf we already have
have_txt = set(f for f in glob.glob(Config.txt_dir + "**/**/*.txt", recursive=True) ) # get list of all txt we already have
print('len(have_pdf)',len(have_pdf))
print('len(have_txt)',len(have_txt))

numok = 0
numtot = 0
db = pickle.load(open(Config.db_path, 'rb'))
for pid,j in db.items():
  if not 20 <= int( dir_basename_from_pid(pid,j).split("/")[0][:2]) <= 80: 
    continue # not between years 1980 and 2019
  pdfs = [x['href'] for x in j['links'] if x['type'] == 'application/pdf']
  assert len(pdfs) == 1
  pdf_url = pdfs[0] + '.pdf'
  basename = pdf_url.split('/')[-1]
  fname = os.path.join(Config.pdf_dir,dir_basename_from_pid(pid,j)+'.pdf')
  pdf_url = 'http://export.arxiv.org/pdf/'+ basename

  #print('pdf_url',pdf_url)
  #print('basename',basename)
  #print('dir_basename_from_pid(pid,j)',dir_basename_from_pid(pid,j))
  if os.path.join(Config.txt_dir,dir_basename_from_pid(pid,j)+'.txt') in have_txt \
     or os.path.join(Config.pdf_dir,dir_basename_from_pid(pid,j)+'.pdf') in have_pdf:
    #print('found')
    continue
  #print('not_found',os.path.join(Config.txt_dir,dir_basename_from_pid(pid,j)+'.txt'))
  #print('int(dir_basename_from_pid(pid,j).split("/")[0][:2])',dir_basename_from_pid(pid,j).split("/")[0][:2]) 

  # try retrieve the pdf
  numtot += 1

  if numtot%4==0: time.sleep(1 + random.uniform(0,0.1)) # as per arXive guidelines
  if numtot%500==0: time.sleep(20 + random.uniform(0,0.1)) # was banned before after a 1000...
  
  print('fetching %s into %s' % (pdf_url, fname))
  try:
    req = urlopen(pdf_url, None, timeout_secs)
    with open(fname, 'wb') as fp:
      shutil.copyfileobj(req, fp)
    time.sleep(random.uniform(0,0.1))
    numok+=1
  except Exception as e:
    print('error downloading: ', pdf_url)
    print(e)
  
  print('%d/%d of %d downloaded ok.' % (numok, numtot, len(db)))
  
print('final number of papers downloaded okay: %d/%d' % (numok, len(db)))
