"""
Reads txt files of all papers and prints out their filenames.
"""
import os
import pickle

from utils import Config, safe_pickle_dump

# read database
db = pickle.load(open(Config.db_path, 'rb'))

# read all text files for all papers into memory
txt_paths, pids = [], []
for pid,j in db.items() :
  if j['_rawid'][:4].isdigit() and '.' in j['_rawid']: 
      print(j['_rawid'][:4]+'/'+j['_rawid']+'.pdf')
  elif '/' in j['_rawid']:
      print(j['_rawid'].split("/")[1][:4]+'/'+"".join(j['_rawid'].split("/"))+'.pdf')
  else: 
      print(j['_rawid'][:4]+'/'+j['arxiv_primary_category']['term'].split(".")[0]+j['_rawid']+'.pdf')

