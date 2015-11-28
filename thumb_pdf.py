# use imagemagick to convert 
# them all to a sequence of thumbnail images
# requires sudo apt-get install imagemagick

import os
import os.path

os.system('mkdir -p static/thumbs')
os.system('rm static/thumbs/*')

relpath = "pdf"
allFiles = os.listdir(relpath)
pdfs = [x for x in allFiles if x.endswith(".pdf")]

for p in pdfs:
  fullpath = os.path.join(relpath, p)
  outpath = os.path.join('static', 'thumbs', p + '.jpg')

  if os.path.isfile(outpath): continue # SKIP

  print "processing " + p

  # this is a mouthful... 
  # take first 8 pages of the pdf ([0-7]), since 9th page are references
  # tile them horizontally, use JPEG compression 80, trim the borders for each image
  #cmd = "montage %s[0-7] -mode Concatenate -tile x1 -quality 80 -resize x230 -trim %s" % (fullpath, "thumbs/" + f + ".jpg")
  #print "EXEC: " + cmd
  
  cmd = "convert %s[0-7] -thumbnail x180 test.png" % (fullpath, )
  os.system(cmd)
  cmd = "montage -mode concatenate -quality 80 -tile x1 test-*.png %s" % (outpath, )
  os.system(cmd)
  print "EXEC: " + cmd
  

# an alternate, more roundabout alternative that is worse and requires temporary files, yuck!
#cmd = "convert -thumbnail x200 %s[0-7] test.png" % (fullpath, )
# os.system(cmd)
#cmd = "montage -mode concatenate -quality 80 -tile x1 test-*.png %s" % ("thumbs/" + f + ".jpg", )
# os.system(cmd)
