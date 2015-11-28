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
  cmd = "pdftotext %s %s" % (pdf_path, txt_path)
  print '%d/%d %s' % (i, len(files), cmd)
  os.system(cmd)
