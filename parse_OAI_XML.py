
"""
Reads arXiv OAI-arXivRAW XML metadata and converts it into the same format as
produced by Karpathy's fetch_papers.py scripts which fetches from the API.

The script is intended to enrich an existing database pickle (by default db.p),
so this file will be loaded first, and then new results will be added to it.
"""

import time
import dateutil
import dateutil.parser
import datetime
import pickle
import random
import argparse
import urllib.request
import re
import requests

from utils import Config, safe_pickle_dump
from lxml import etree, objectify

#Converts the OAI metadata to API format and then adds to database
def parse_xml(response):
        
      # lets load the existing database to memory
      try:
        db = pickle.load(open(Config.db_path, 'rb'))
      except Exception as e:
        print('error loading existing database:')
        print(e)
        print('starting from an empty database')
        db = {}
      
      print('database has %d entries at start' % (len(db), ))  
      
      OAI = "{http://www.openarchives.org/OAI/2.0/}"
      ARXIV = "{http://arxiv.org/OAI/arXivRaw/}"
        
      parse = objectify.parse(response)
      
      num_added = 0
      num_skipped = 0
      
      root = parse.getroot()
      record_list = root.find(OAI+'ListRecords').findall(OAI+"record")
      
      for record in record_list:
        info = record.metadata.find(ARXIV+"arXivRaw")
        
        versions = info.findall(ARXIV+"version")
        version_num = len(versions)
        
        published_version = info.find(ARXIV+"version[@version='v1']")
        latest_version = info.find(ARXIV+"version[@version='v"+str(version_num)+"']")
        
        published_parsed = dateutil.parser.parse(published_version.date.text)
        updated_parsed = dateutil.parser.parse(latest_version.date.text)
        published = published_parsed.strftime('%Y-%m-%d')
        updated = updated_parsed.strftime('%Y-%m-%d')
        
        authors = []
        author_list = info.authors.text.replace(', and ',', ')
        author_list = info.authors.text.replace(' and ',', ')
        author_list = author_list.split(', ')
        for author in author_list:
            authors.append({'name': author})
        
        cats = info.categories.text.split()
        primary_cat = {'term': cats[0]}
        tags = []
        for cat in cats:
            tags.append({'term': cat})
        
        rawid = info.id.text
        
        id_url = 'http://arxiv.org/abs/'+info.id.text
        
        if hasattr(info, 'doi'):
            doi = info.doi.text
        else:
            doi = ''
            
        if hasattr(info, 'journal-ref'):
            journal = info.find(ARXIV+'journal-ref').text
        else:
            journal = ''
            
        if hasattr(info, 'comments'):
            comment = info.find(ARXIV+'comments').text
        else:
            comment = ''
         
        links = [{'href': 'http://arxiv.org/abs/'+rawid+'v'+str(version_num),
                  'rel': 'alternate',
                  'type': 'text/html'},
                   {'href': 'http://arxiv.org/pdf/'+rawid+'v'+str(version_num),
                    'rel': 'related',
                    'title': 'pdf',
                    'type': 'application/pdf'}]
                                    
        j = {       'published': published,
                    'updated': updated,
                    'updated_parsed': updated_parsed,
                    'published_parsed': published_parsed,
                    'authors': authors,
                    'tags': tags,
                    'arxiv_primary_category': primary_cat,
                    'arxiv_doi': doi,
                    'arxiv_journal_ref': journal,
                    'id': id_url,
                    'link': id_url,
                    'links': links,
                    '_rawid': rawid,
                    '_version': version_num,
                    'title': info.title.text,
                    'summary': info.abstract.text,
                    'arxiv_comment': comment,
                    }
            
        # add to our database if we didn't have it before, or if this is a new version
        if not rawid in db or j['_version'] > db[rawid]['_version']:
          db[rawid] = j
          print('Updated %s added %s' % (j['updated'].encode('utf-8'), j['title'].encode('utf-8')))
          num_added += 1
        else:
          num_skipped += 1
    
      # print some information
      print('Added %d papers, already had %d.' % (num_added, num_skipped))
      
      # save the database before we quit, if we found anything new
      print('Saving database with %d papers to %s' % (len(db), Config.db_path))
      safe_pickle_dump(db, Config.db_path)
    
      return 


if __name__ == "__main__":

  # parse input arguments
  parser = argparse.ArgumentParser()
  parser.add_argument('-f','--file', type=str,
                      help='xml file to be read into database', required=True)
  args = parser.parse_args()

  #parse and upload metadata to database
  parse_xml(args.file)
  
  
