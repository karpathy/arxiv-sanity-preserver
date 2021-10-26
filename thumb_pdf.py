"""
Use imagemagick to convert all pfds to a sequence of thumbnail images
requires: sudo apt-get install imagemagick
"""
import datetime
import os, sys
import time
import shutil
from subprocess import Popen

from utils import Config, get_left_time_str


def create_thumbnail(pdf_path, thumb_path):
    try:
        # take first 8 pages of the pdf ([0-7]), since 9th page are references
        # tile them horizontally, use JPEG compression 80, trim the borders for each image
        # cmd = "montage %s[0-7] -mode Concatenate -tile x1 -quality 80 -resize x230 -trim %s" % (pdf_path, "thumbs/" + f + ".jpg")
        # print "EXEC: " + cmd

        # nvm, below using a roundabout alternative that is worse and requires temporary files, yuck!
        # but i found that it succeeds more often. I can't remember wha thappened anymore but I remember
        # that the version above, while more elegant, had some problem with it on some pdfs. I think.

        # erase previous intermediate files thumb-*.png in the tmp directory
        if os.path.isfile(os.path.join(Config.tmp_dir, 'thumb-0.png')):
            for i in range(8):
                f = os.path.join(Config.tmp_dir, 'thumb-%d.png' % (i,))
                f2 = os.path.join(Config.tmp_dir, 'thumbbuf-%d.png' % (i,))
                if os.path.isfile(f):
                    os.replace(f, f2)
        if os.path.isfile(os.path.join(Config.tmp_dir, 'thumb.png')):
            os.replace(os.path.join(Config.tmp_dir, 'thumb.png'), os.path.join(Config.tmp_dir, 'thumbbuf.png'))

        pp = Popen(['magick', '%s[0-7]' % (pdf_path,), '-define', 'png:color-type=6', '-thumbnail', 'x156',
                    os.path.join(Config.tmp_dir, 'thumb.png')])
        t0 = time.time()
        while time.time() - t0 < 300:  # give it 5 minutes deadline
            ret = pp.poll()
            if not (ret is None):
                # process terminated
                break
            time.sleep(0.1)
        ret = pp.poll()
        if ret is None:
            print("magick command did not terminate in 5 minutes, terminating.")
            pp.terminate()  # give up

        if os.path.isfile(os.path.join(Config.tmp_dir, 'thumb-0.png')):
            cmd = "magick montage -mode concatenate -quality 80 -tile x1 %s %s" % (
                os.path.join(Config.tmp_dir, 'thumb-*.png'), thumb_path)
            print(cmd)
            os.system(cmd)
        elif os.path.isfile(os.path.join(Config.tmp_dir, 'thumb.png')):
            cmd = 'magick convert %s -background white -flatten %s' % (
                os.path.join(Config.tmp_dir, 'thumb.png'), thumb_path)
            os.system(cmd)
        else:
            # failed to render pdf, replace with missing image
            missing_thumb_path = os.path.join('static', 'missing.jpg')
            os.system('cp %s %s' % (missing_thumb_path, thumb_path))
            print("could not render pdf, creating a missing image placeholder")

        time.sleep(0.01)  # silly way for allowing for ctrl+c termination
    except KeyboardInterrupt:
        print('keyboard interrupted while converting %s,clearing buffer' % pdf_path)
        os.remove(thumb_path)
        sys.exit()
    except Exception as e:
        print('error converting:%s,%s' % (pdf_path, str(e)))


def create_thumbnails(pdf_files, time_max_count=100):
    print("%d pdf files need to make thumbnail,starting in 3 seconds" % len(pdf_files))
    time.sleep(3)
    time_records = []
    num_left = len(pdf_files)
    for i, p in enumerate(pdf_files):
        time_start = datetime.datetime.now()
        pdf_path = os.path.join(Config.pdf_dir, p)
        thumb_path = os.path.join(Config.thumbs_dir, p + '.jpg')

        create_thumbnail(pdf_path, thumb_path)

        time_take = datetime.datetime.now() - time_start
        num_left -= 1
        if len(time_records) > time_max_count:
            time_records.pop(0)
        time_records.append(time_take.seconds)
        print("%d/%d %s thumbnail created, %s." % (i + 1, len(pdf_files), p, get_left_time_str(time_records, num_left)))


def check_requirement():
    # make sure imagemagick is installed
    if not shutil.which('magick'):  # shutil.which needs Python 3.3+
        print("ERROR: you don\'t have imagemagick installed. Install it first before calling this script")
        sys.exit()

    # create if necessary the directories we're using for processing and output
    if not os.path.exists(Config.thumbs_dir): os.makedirs(Config.thumbs_dir)
    if not os.path.exists(Config.tmp_dir): os.makedirs(Config.tmp_dir)


def need_to_convert_pdf_files():
    result = []

    # fetch all pdf filenames in the pdf directory
    all_pdf_files = [x for x in os.listdir(Config.pdf_dir) if x.endswith('.pdf')]  # filter to just pdfs, just in case
    all_jpg_files = [x for x in os.listdir(Config.thumbs_dir) if
                     x.endswith('.jpg')]  # filter to just pdfs, just in case
    all_pdf_files.sort(reverse=True)
    tmp_jpgs = set(all_jpg_files)
    for pdf in all_pdf_files:
        set_len_before = len(tmp_jpgs)
        tmp_jpgs.add(pdf + ".jpg")
        if set_len_before != len(tmp_jpgs):
            result.append(pdf)

    return result


if __name__ == "__main__":
    check_requirement()

    pdf_files = need_to_convert_pdf_files()

    create_thumbnails(pdf_files)
