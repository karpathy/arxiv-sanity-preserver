"""

"""
import os
import time
import pickle
import random
import argparse
import urllib.request
import feedparser
import subprocess
from pprint import pprint
from whoswho import who
from subprocess import check_output, STDOUT, CalledProcessError
from utils import Config, safe_pickle_dump
import sys
from neo4j.v1 import GraphDatabase
    
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "1234"))

def add_author(tx, name, title):
    tx.run("MERGE (a:Person {name: $name}) "
           "MERGE (paper:Paper {title: $title})"
           "MERGE (a)-[:AUTHOR]->(paper)",
           name=name, title=title)


def add_coauthor(tx, name, title):
    tx.run("MERGE (a:Person {name: $name}) "
           "MERGE (paper:Paper {title: $title})"
           "MERGE (a)-[:COAUTHOR]->(paper)",
           name=name, title=title)

with driver.session() as session:
    with open("all_papers.csv", "r") as ins:
        for line in ins:
            info = line.split(",")
            if info[1]=="author":
                session.write_transaction(add_author,info[0],info[2])
            elif info[1]=="co-author":
                session.write_transaction(add_coauthor,info[0],info[2])
            
    #    title = info[1].replace('`', '').replace('\'', '')
    #    first_author = info[2]
    #    first_author = first_author.encode("ascii","ignore") .decode("utf-8", "strict").replace('`', '').replace('\'', '')
    #    print(title,first_author)
# #        cli   = "./scholar.py/scholar.py -c 1 --cookie-file cookie.txt --authors --author \"%s\" --phrase %s" % (first_author, title)

# #        print(cli)
# # #       try:
# #        output = subprocess.check_output(cli, shell=True)
# #       except CalledProcessError as ex:
# #          output = ""
# #          continue

#     #    print (output)

#        authors = output.decode('utf8').split(",")

#        for name in info[2:] :
#           for i in range(0, len(authors)):
#              if (who.match(name, authors[i])) :
#                 print( "%s, %s" %(name, authors[i+1]))

#        sys.stdout.flush();  
#        time.sleep(random.uniform(20, 60))  # Random float x, 1.0 <= x < 10.0
#        count += 1
#        if count % 100 == 0 :
#           time.sleep(600)
#        else:
#           print (count)