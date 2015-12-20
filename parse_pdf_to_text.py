import time
import os

import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--tet", action='store_true',
                    help="Use PDFLib Text and Image Extraction Toolkit(TET) for text extraction.")

parser.add_argument("--tet_eval_mode", action='store_true',
                    help="Use PDFLib Text and Image Extraction Toolkit(TET) in evaluation mode. "
                         "PDFlib TET can be evaluated without a license, "
                         "but will only process PDF documents with up to 10 pages and 1 MB size "
                         "unless a valid license key is applied. "
                         "Pdf files are split into single pages to use TET in evalution mode.")

args = parser.parse_args()

os.system('mkdir -p txt') # ?
files = os.listdir('pdf')

if args.tet:
  cmd = "tet --samedir pdf/*.pdf"
  os.system(cmd)
  for i,f in enumerate(files):
    if f.endswith('.txt') and (not f.endswith('.pdf.txt')):
      os.rename(f, f[0:-4]+'.pdf.txt')
elif args.tet_eval_mode:
  from PyPDF2 import PdfFileWriter, PdfFileReader

  for f in files:
    if f.endswith('.pdf'):
      pdf_path = os.path.join('pdf', f)
      inputpdf = PdfFileReader(file(pdf_path, "rb"))

      #split the pdf file into single pages to use tet in evaluation mode
      for i in xrange(inputpdf.numPages):
        output = PdfFileWriter()
        output.addPage(inputpdf.getPage(i))
        outputStream = file(pdf_path[0:-4] + "-%s.pdf" % i, "wb")
        output.write(outputStream)
        outputStream.close()

      # convert to text files by pages
      for i in xrange(inputpdf.numPages):
        cmd = "tet --samedir "+ os.path.join('pdf', f[0:-4]+"-%s.pdf"%i)
        os.system(cmd)

      # combine the text files
      sep = ' '
      cmd = sep.join(["cat"] + [pdf_path[0:-4]+"-%s.txt"%i for i in xrange(inputpdf.numPages)] + ['> '+pdf_path+'.txt'])
      os.system(cmd)

      # remove temporary files
      cmd = 'rm '+pdf_path[0:-4]+'-*.txt '+pdf_path[0:-4]+'-*.pdf'
      os.system(cmd)
else:
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
