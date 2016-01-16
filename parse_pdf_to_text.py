"""
Very simple script that simply iterates over all files pdf/f.pdf
and create a file txt/f.pdf.txt that contains the raw text, extracted
using the "pdftotext" command. If a pdf cannot be converted, this
script will not produce the output file.
"""

import cPickle as pickle
import urllib2
import shutil
import time
import os
import random

os.system('mkdir -p txt') # ?

files = os.listdir('pdf')
for i,f in enumerate(files):
  pdf_path = os.path.join('pdf', f)
  txt_path = os.path.join('txt', f+'.txt')
  if not os.path.isfile(txt_path):
    cmd = "pdftotext %s %s" % (pdf_path, txt_path)
    print '%d/%d %s' % (i, len(files), cmd)
    os.system(cmd)
  else:
    print 'skipping %s, already exists.' % (pdf_path, )
  time.sleep(0.05) # silly way for allowing for ctrl+c termination
  