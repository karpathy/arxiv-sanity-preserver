"""
Very simple script that simply iterates over all files pdf/f.pdf
and create a file txt/f.pdf.txt that contains the raw text, extracted
using the "pdftotext" command. If a pdf cannot be converted, this
script will not produce the output file.
"""
from __future__ import print_function

try:
  import pickle as pickle
except:
  import cPickle as pickle

import shutil
import time
import os
import random

def extract_text(in_dir = 'pdf', out_dir = 'txt'):
  list_of_failures = []

  os.system('mkdir -p %s' % (out_dir)) # ?
  have = set(os.listdir(out_dir))
  files = os.listdir(in_dir)
  for i,f in enumerate(files, start=1):
    pdf_path = os.path.join(in_dir, f)
    txt_basename = f + '.txt'
    txt_path = os.path.join(out_dir, txt_basename)
    if not txt_basename in have:
      cmd = "pdftotext %s %s" % (pdf_path, txt_path)
      os.system(cmd)
      print('%d/%d %s' % (i, len(files), cmd))

      # check output was made
      if not os.path.isfile(txt_path):
        # there was an error with converting the pdf
        print("Error with file: ", f)
        list_of_failures.append(f)
        os.system('touch ' + txt_path) # create empty file, but it's a record of having tried to convert

      time.sleep(0.02) # silly way for allowing for ctrl+c termination
    else:
      print('skipping %s, already exists.' % (pdf_path, ))
  return list_of_failures

def main():
  list_of_failures = extract_text()
  for fail in list_of_failures:
    print("File %s Failed." % fail)

if __name__ == '__main__':
  main()
