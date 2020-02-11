"""
Queries arxiv OAI and downloads paper XML data.

This script was adataped from another arXiv-metadata project on github. I 
should cite them here, but I need to find the url again.
"""

import os
import time
import datetime
import dateutil
import pickle
import random
import argparse
import urllib.request
import re
import requests

from utils import Config, safe_pickle_dump
from lxml import etree, objectify
from parse_OAI_XML import parse_xml

if __name__ == "__main__":

  # parse input arguments
  parser = argparse.ArgumentParser()
  parser.add_argument('--set', type=str,
          default='physics:cond-mat',
                      #default='physics:hep-th',
                      help='category used for arxiv OAI of form physics:arxivcat')
  parser.add_argument('--from-date', type=str, default=datetime.date.isoformat(datetime.date.today()-datetime.timedelta(1)), help='Start date in YYYY-MM-DD')
  parser.add_argument('--until-date', type=str, default=datetime.date.isoformat(datetime.date.today()), help='End date in YYYY-MM-DD, default is today')
  args = parser.parse_args()

  # misc hardcoded variables
  resume_re = re.compile(r".*<resumptionToken.*?>(.*?)</resumptionToken>.*")
  base_url = 'http://export.arxiv.org/oai2?' # base api query url
  req = {u"verb": "ListRecords",
           u"metadataPrefix": u"arXivRaw", u"set": args.set, u"from": args.from_date, u"until": args.until_date,}
  print('Searching arXiv with query: '+str(req))

  max_tries = 10
  
  num_added_total = 0
  failures = 0
  count = 0
  while True:
     # Send the request.
    r = requests.post(base_url, data=req)
    
    # Handle the response.
    code = r.status_code
    print("Received Response Code:", code)
  
    if code == 503:
            # Asked to retry
            to = int(r.headers["retry-after"])
            print(u"Got 503. Retrying after {0:d} seconds.".format(to))

            time.sleep(to)
            failures += 1
            if failures >= max_tries:
                print(u"Failed too many times...")
                break

    elif code == 200:
        failures = 0

        # Write to file.
        content = r.text
        #print(content)
        count += 1
        
        #Save a backup of xml from arXiv in case screw up parsing (don't bother them too often)
        file_name = u"raw"+datetime.date.isoformat(datetime.date.today())+"-{0:08d}.xml".format(count)
        print(u"Writing to: {0}".format(file_name))
        with open(file_name, u"w") as f:
            f.write(content)

        #Call a function from parse_xml.py to convert OAI-RAW to API format
        parse_xml(file_name)
        #num_added_total += num_added

        # Look for a resumption token.
        token = resume_re.search(content)
        if token is None:
            break
        token = token.groups()[0]

        # If there isn't one, we're all done.
        if token == "":
            print(u"All done.")
            break

        print(u"Resumption token: {0}.".format(token))

        # If there is a resumption token, rebuild the request.
        req = {u"verb": u"ListRecords",
               u"resumptionToken": token}

        # Pause so as not to get banned.
        to = 20
        print(u"Sleeping for {0:d} seconds so as not to get banned."
                .format(to))
        time.sleep(to)

    else:
        # Wha happen'?
        r.raise_for_status()
    
