"""
Use imagemagick to convert all pfds to a sequence of thumbnail images
requires: sudo apt-get install imagemagick
"""
import datetime
import os, sys
import threading
import time
import shutil
from subprocess import Popen

from utils import Config, get_left_time_str


def create_thumbnail(thread_number, pdf_path, thumb_path):
    time.sleep(0.1)  # thread sleep
    try:
        if os.path.isfile(os.path.join(Config.tmp_dir, thread_number, 'thumb-0.png')):
            for i in range(8):
                f = os.path.join(Config.tmp_dir, thread_number, 'thumb-%d.png' % (i,))
                f2 = os.path.join(Config.tmp_dir, thread_number, 'thumbbuf-%d.png' % (i,))
                if os.path.isfile(f):
                    os.replace(f, f2)
        if os.path.isfile(os.path.join(Config.tmp_dir, thread_number, 'thumb.png')):
            os.replace(os.path.join(Config.tmp_dir, thread_number, 'thumb.png'),
                       os.path.join(Config.tmp_dir, 'thumbbuf.png'))

        pp = Popen(['magick', '%s[0-7]' % (pdf_path,), '-define', 'png:color-type=6', '-thumbnail', 'x156',
                    os.path.join(Config.tmp_dir, thread_number, 'thumb.png')])
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

        if os.path.isfile(os.path.join(Config.tmp_dir, thread_number, 'thumb-0.png')):
            cmd = "magick montage -mode concatenate -quality 80 -tile x1 %s %s" % (
                os.path.join(Config.tmp_dir, thread_number, 'thumb-*.png'), thumb_path)
            print(cmd)
            os.system(cmd)
        elif os.path.isfile(os.path.join(Config.tmp_dir, thread_number, 'thumb.png')):
            cmd = 'magick convert %s -background white -flatten %s' % (
                os.path.join(Config.tmp_dir, thread_number, 'thumb.png'), thumb_path)
            os.system(cmd)
        else:
            # failed to render pdf, replace with missing image
            missing_thumb_path = os.path.join('static', 'missing.jpg')
            shutil.copy(missing_thumb_path, thumb_path)
            print("could not render pdf, creating a missing image placeholder")

        time.sleep(0.01)  # silly way for allowing for ctrl+c termination
    except KeyboardInterrupt:
        print('keyboard interrupted while converting %s,clearing buffer' % pdf_path)
        os.remove(thumb_path)
        sys.exit()
    except Exception as e:
        print('error converting:%s,%s' % (pdf_path, str(e)))


def create_thumbnails(thread_number, pdf_files, time_max_count=100):
    time.sleep(3)
    time_records = []
    num_left = len(pdf_files)

    for i, p in enumerate(pdf_files):
        time_start = datetime.datetime.now()
        pdf_path = os.path.join(Config.pdf_dir, p)
        thumb_path = os.path.join(Config.thumbs_dir, p + '.jpg')

        create_thumbnail(thread_number, pdf_path, thumb_path)

        time_take = datetime.datetime.now() - time_start
        num_left -= 1
        if len(time_records) > time_max_count:
            time_records.pop(0)
        time_records.append(time_take.seconds)
        print("thread %s: %d/%d %s thumbnail created, %s." % (
            thread_number, i + 1, len(pdf_files), p, get_left_time_str(time_records, num_left)))


def thread_create_thumbnails(pdf_files):
    thread_len = len(pdf_files)
    print("starting %d threads in 3 seconds" % (thread_len))
    time.sleep(3)
    threads = []
    for i in range(thread_len):
        t = threading.Thread(target=create_thumbnails, args=[str(i), pdf_files[i]], daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()


def check_requirement(max_threads):
    # make sure imagemagick is installed
    if not shutil.which('magick'):  # shutil.which needs Python 3.3+
        print("ERROR: you don\'t have imagemagick installed. Install it first before calling this script")
        sys.exit()

    # create if necessary the directories we're using for processing and output
    if not os.path.exists(Config.thumbs_dir): os.makedirs(Config.thumbs_dir)
    if not os.path.exists(Config.tmp_dir): os.makedirs(Config.tmp_dir)
    for i in range(max_threads):
        if not os.path.exists(os.path.join(Config.tmp_dir, str(i))): os.makedirs(os.path.join(Config.tmp_dir, str(i)))


def need_to_convert_pdf_files(max_threads):
    result = [[] for i in range(max_threads)]

    # fetch all pdf filenames in the pdf directory
    all_pdf_files = [x for x in os.listdir(Config.pdf_dir) if x.endswith('.pdf')]  # filter to just pdfs, just in case
    all_jpg_files = [x for x in os.listdir(Config.thumbs_dir) if
                     x.endswith('.jpg')]  # filter to just pdfs, just in case
    all_pdf_files.sort(reverse=True)
    tmp_jpgs = set(all_jpg_files)
    idx = 0
    for pdf in all_pdf_files:
        set_len_before = len(tmp_jpgs)
        tmp_jpgs.add(pdf + ".jpg")
        if set_len_before != len(tmp_jpgs):
            result[idx].append(pdf)
            idx = idx + 1 if idx < max_threads - 1 else 0

    return result


if __name__ == "__main__":
    max_thread = os.cpu_count() // 2  # using half of cpu

    check_requirement(max_thread)

    pdf_files = need_to_convert_pdf_files(max_thread)

    thread_create_thumbnails(pdf_files)
