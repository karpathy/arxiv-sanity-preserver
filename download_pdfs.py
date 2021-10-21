import collections
import datetime
import os
import re
import sys
import threading
import time
import pickle
import shutil
import random
from urllib.request import urlopen

from utils import Config, get_left_time_str

TMP_SUFFIX = ".tmp"
RESTART = True


def cmd_listener():
    while True:
        cmd = sys.stdin.readline()
        print("cmd received:%s" % cmd)
        if cmd == "restart\n":
            global RESTART
            RESTART = True


def cache_clear(file_name):
    if os.path.exists(file_name):
        print("cache file %s found,cleaning buffer..." % file_name)
        os.remove(file_name)
    elif os.path.exists(file_name + TMP_SUFFIX):
        print("cache file %s found,cleaning buffer..." % (file_name + TMP_SUFFIX))
        os.remove(file_name + TMP_SUFFIX)
    else:
        print("cache %s not found, no need to clean..." % file_name)


def download_paper(url, dst_name):
    timeout_secs = 10  # after this many seconds we give up on a paper
    try:
        print('fetching %s into %s' % (url, dst_name))
        req = urlopen(url, None, timeout=timeout_secs)
        if req.headers['Content-Type'] == 'application/pdf':
            with open(dst_name + TMP_SUFFIX, 'wb') as fp:
                shutil.copyfileobj(req, fp)
            os.rename(dst_name + TMP_SUFFIX, dst_name)
            success = True
        else:
            if 'Pragma' in req.headers.keys():
                print("arxiv prevent caching, retry later")
                success = False
            else:
                missing_pdf_path = os.path.join('static', 'missing.pdf')
                shutil.copyfile(missing_pdf_path, dst_name)
                print("could not find pdf, creating a missing pdf placeholder")
                success = True
    except Exception as e:
        print('error downloading:%s,%s' % (url, str(e)))
        cache_clear(dst_name)
        success = False
    except KeyboardInterrupt:
        print('keyboard interrupted while downloading %s' % url)
        cache_clear(dst_name)
        sys.exit(-1)
    return success


def thread_download(db_items, start_idx, batch_size, time_max_count=100):
    global RESTART
    end_idx = min(start_idx + batch_size, len(db_items))
    loop, need_to_download, time_records = 0, db_items[start_idx:end_idx], []
    need_to_download_len = len(need_to_download)
    while need_to_download_len > 0:
        print('starting download for %dth loop' % loop)
        num_ok, failed_records = 0, []
        for idx in range(need_to_download_len):
            if RESTART:
                return

            time_start = datetime.datetime.now()

            pdf_url = need_to_download[idx]
            basename = get_file_info(pdf_url)[0]
            fname = os.path.join(Config.pdf_dir, basename)

            if download_paper(pdf_url, fname):
                num_ok += 1
                time_take = datetime.datetime.now() - time_start
                if len(time_records) > time_max_count:
                    time_records.pop(0)
                time_records.append(time_take.seconds)
            else:
                failed_records.append((idx, pdf_url))
                check_forbidden(failed_records)
            if len(time_records) > 0:
                print(
                    '%d/%d downloaded, %s' % (
                        num_ok, need_to_download_len, get_left_time_str(time_records, need_to_download_len - num_ok)))

        loop += 1
        print(
            'papers downloaded okay: %d/%d, %s' % (
                num_ok, need_to_download_len,
                'exiting' if num_ok == need_to_download_len else 'retrying'))
        need_to_download = [x for idx, x in failed_records]
        need_to_download_len = len(need_to_download)
    RESTART = True


def check_forbidden(failed_records, sleep_secs=30):
    # arxiv added some constrain for long term download
    if len(failed_records) > 3:
        idx_continuous = failed_records[-1][0] == failed_records[-2][0] + 1 == failed_records[-3][0] + 2
        same_contents = get_file_info(failed_records[-1][1])[1] == get_file_info(failed_records[-2][1])[1] == \
                        get_file_info(failed_records[-3][1])[1]
        if idx_continuous and not same_contents:
            print('===============forbidden detected,sleep for %d seconds===============' % sleep_secs)
            time.sleep(sleep_secs + random.uniform(0, 0.1))


def get_file_info(pdf_url):
    basename = pdf_url.split('/')[-1]
    info = basename.replace(".pdf", "").split('v')
    raw_id = info[0]
    version = info[1]
    return basename, raw_id, version


def get_need_download():
    db = pickle.load(open(Config.db_path, 'rb'))
    db = collections.OrderedDict(sorted(db.items(), reverse=True))
    have = set(os.listdir(Config.pdf_dir))  # get list of all pdfs we already have

    db_items = []
    for pid, j in db.items():
        for i in range(1, int(j['_version']) + 1):
            basename = j['_rawid'] + 'v' + str(i) + '.pdf'
            if basename not in have:
                pdfs = [x['href'] for x in j['links'] if x['type'] == 'application/pdf']
                pdf_url = pdfs[0] + '.pdf'
                url_root = re.sub('[^/]*$', '', pdf_url)
                db_items.append(url_root + basename)

    return db_items


if __name__ == "__main__":
    if not os.path.exists(Config.pdf_dir): os.makedirs(Config.pdf_dir)

    threading.Thread(target=cmd_listener, daemon=True).start()

    while RESTART:
        db_items = get_need_download()
        n_threads = 1
        batch_size = len(db_items) // n_threads
        if len(db_items) > 0:
            RESTART = False
            print('%d papers need to download,starting in 3 seconds...' % (len(db_items)))
            time.sleep(3)
            thread_download(db_items, 0, batch_size)
        else:
            RESTART = True
            print("0 papers need to download,waiting for one hour...")
            time.sleep(3600)  # empty loop for download finished
        print("restarting download process...")
