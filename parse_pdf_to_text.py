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

have = os.listdir('txt')
files = os.listdir('pdf')
for i,f in enumerate(files):
  pdf_path = os.path.join('pdf', f)
  txt_basename = f + '.txt'
  txt_path = os.path.join('txt', txt_basename)
  if not txt_basename in have:
    cmd = "pdftotext %s %s" % (pdf_path, txt_path)
    os.system(cmd)
    print '%d/%d %s' % (i, len(files), cmd)

    # check output was made
    if not os.path.isfile(txt_path):
      # there was an error with converting the pdf
      os.system('touch ' + txt_path) # create empty file, but it's a record of having tried to convert

    time.sleep(0.02) # silly way for allowing for ctrl+c termination
  else:
    print 'skipping %s, already exists.' % (pdf_path, )
