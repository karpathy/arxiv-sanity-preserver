# use imagemagick to convert 
# them all to a sequence of thumbnail images
# requires sudo apt-get install imagemagick

import os
import os.path
import time
from subprocess import Popen

os.system('mkdir -p static/thumbs')
os.system('mkdir -p tmp') # for intermediate files

relpath = "pdf"
allFiles = os.listdir(relpath)
pdfs = [x for x in allFiles if x.endswith(".pdf")]

for i,p in enumerate(pdfs):
  fullpath = os.path.join(relpath, p)
  outpath = os.path.join('static', 'thumbs', p + '.jpg')

  if os.path.isfile(outpath): 
    print 'skipping %s, exists.' % (fullpath, )
    continue

  print "%d/%d processing %s" % (i, len(pdfs), p)

  # take first 8 pages of the pdf ([0-7]), since 9th page are references
  # tile them horizontally, use JPEG compression 80, trim the borders for each image
  #cmd = "montage %s[0-7] -mode Concatenate -tile x1 -quality 80 -resize x230 -trim %s" % (fullpath, "thumbs/" + f + ".jpg")
  #print "EXEC: " + cmd
  
  # nvm, below using a roundabout alternative that is worse and requires temporary files, yuck!
  # but i found that it succeeds more often. I can't remember wha thappened anymore but I remember
  # that the version above, while more elegant, had some problem with it on some pdfs. I think.

  # erase previous intermediate files test-*.png
  if os.path.isfile('tmp/test-0.png'):
    for i in xrange(8):
      f = 'tmp/test-%d.png' % (i,)
      f2= 'tmp/testbuf-%d.png' % (i,)
      if os.path.isfile(f):
        cmd = 'mv %s %s' % (f, f2)
        os.system(cmd)
        # okay originally I was going to issue an rm call, but I am too terrified of
        # running scripted rm queries, so what we will do is instead issue a "mv" call
        # to rename the files. That's a bit safer, right? We have to do this because if
        # some papers are shorter than 8 pages, then results from previous paper will
        # "leek" over to this result, through the intermediate files.

  # spawn async. convert can unfortunately enter an infinite loop, have to handle this
  pp = Popen(['convert', "%s[0-7]" % (fullpath, ), "-thumbnail", "x156", "tmp/test.png"])
  t0 = time.time()
  while time.time() - t0 < 15: # give it 15 seconds deadline
    ret = pp.poll()
    if not (ret is None):
      # process terminated
      break
    time.sleep(0.1)
  ret = pp.poll()
  if ret is None:
    # we did not terminate in 5 seconds
    pp.terminate() # give up

  if not os.path.isfile('tmp/test-0.png'):
    # failed to render pdf, replace with missing image
    os.system('cp %s %s' % ('static/thumbs/missing.jpg', outpath))
    print 'could not render pdf, creating a missing image placeholder'
  else:
    cmd = "montage -mode concatenate -quality 80 -tile x1 tmp/test-*.png %s" % (outpath, )
    print cmd
    os.system(cmd)

  time.sleep(0.01) # silly way for allowing for ctrl+c termination
