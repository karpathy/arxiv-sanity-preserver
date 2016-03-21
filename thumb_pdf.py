# use imagemagick to convert 
# them all to a sequence of thumbnail images
# requires sudo apt-get install imagemagick

import os
import os.path
import time
from subprocess import Popen

os.system('mkdir -p static/thumbs')

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

  # spawn async. convert can unfortunately enter an infinite loop, have to handle this
  # convert:
  #	- path/to/file.pdf[start-end] : operate on file, pages from start to end included
  #	- thumbnail [w]x[h]: create a [Width]X[height] thumbnail of the page
  # 	- quality [0-100]: output png quality
  #	- +append : append an image sequence left to right
  #	- path/to/output.png
  pp = Popen([
  	'convert',
	"%s[0-7]" % (fullpath, ),
	"-thumbnail",
	"x156",
	"-quality",
	"80",
	"+append",
	"%s" % (outpath, ),
	])

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

  if not os.path.isfile(outpath):
    # failed to render pdf, replace with missing image
    os.system('cp %s %s' % ('static/thumbs/missing.jpg', outpath))
    print 'could not render pdf, creating a missing image placeholder'

  time.sleep(0.01) # silly way for allowing for ctrl+c termination
