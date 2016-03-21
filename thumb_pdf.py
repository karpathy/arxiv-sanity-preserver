# use imagemagick to convert 
# them all to a sequence of thumbnail images
# requires sudo apt-get install imagemagick

import argparse
import multiprocessing
import os
import os.path
import shutil
import sys
import time
from subprocess import Popen

PDF_DIR = "pdf"

def process_pdf(i, p, total):
  fullpath = os.path.join(PDF_DIR, p)
  outpath = os.path.join('static', 'thumbs', p + '.jpg')

  if os.path.isfile(outpath): 
    print 'skipping %s, thumbnail exists.' % (fullpath, )
    return

  print "%d/%d processing %s" % (i, total, p)

  # take first 8 pages of the pdf ([0-7]), since 9th page are references
  # tile them horizontally, use JPEG compression 80, trim the borders for each image
  #cmd = "montage %s[0-7] -mode Concatenate -tile x1 -quality 80 -resize x230 -trim %s" % (fullpath, "thumbs/" + f + ".jpg")
  #print "EXEC: " + cmd
  
  # nvm, below using a roundabout alternative that is worse and requires temporary files, yuck!
  # but I found that it succeeds more often. I can't remember what happened anymore but I remember
  # that the version above, while more elegant, had some problem with it on some pdfs. I think.

  tmpdir_name = os.path.join("tmp", "tmp-%d" % i)
  if not os.path.exists(tmpdir_name):
    os.mkdir(tmpdir_name)
  # spawn async. convert can unfortunately enter an infinite loop, have to handle this
  cmd = ['convert', "%s[0-7]" % (fullpath, ), "-thumbnail", "x156", os.path.join(tmpdir_name, "test.png")]
  pp = Popen(cmd)
  t0 = time.time()
  while time.time() - t0 < 1200: # give it 2 minutes deadline
    ret = pp.poll()
    if not (ret is None):
      # process terminated
      break
    time.sleep(0.1)
  ret = pp.poll()
  if ret is None:
    # we did not terminate in 5 seconds
    pp.terminate() # give up

  if not os.path.isfile(os.path.join(tmpdir_name, 'test-0.png')):
    # failed to render pdf, replace with missing image
    os.system('cp %s %s' % (os.path.join('static', 'thumbs', 'missing.jpg'), outpath))
    print 'could not render pdf, creating a missing image placeholder'
  else:
    cmd = "montage -mode concatenate -quality 80 -tile x1 %s/test-*.png %s" % (tmpdir_name, outpath, )
    print cmd
    os.system(cmd)
  shutil.rmtree(tmpdir_name)

def main(args):
  parser = argparse.ArgumentParser("Generate thumbnails of pdfs")
  parser.add_argument("-j", metavar="jobs", default=multiprocessing.cpu_count(),
      type=int, help="Maximum number of simultaneous processes")
  options = parser.parse_args(args)

  os.system('mkdir -p static/thumbs')
  os.system('mkdir -p tmp') # for intermediate files

  allFiles = os.listdir(PDF_DIR)
  pdfs = [x for x in allFiles if x.endswith(".pdf")]
  total_pdfs = len(pdfs)

  pool = multiprocessing.Pool(processes=options.j)
  jobs = []
  for i,p in enumerate(pdfs):
    job = pool.apply_async(process_pdf, args=(i,p, total_pdfs))
    jobs.append(job)
  for job in jobs:
    while not job.ready():
        time.sleep(1)
  pool.close()
  pool.join()

if __name__ == "__main__":
  main(sys.argv[1:])
