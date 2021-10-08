import collections
import datetime
import os
import re
import sys
import time
import pickle
import shutil
import random
from urllib.request import urlopen

from utils import Config, get_left_time_str

if not os.path.exists(Config.pdf_dir): os.makedirs(Config.pdf_dir)
have = set(os.listdir(Config.pdf_dir))  # get list of all pdfs we already have

db = pickle.load(open(Config.db_path, 'rb'))
db = collections.OrderedDict(sorted(db.items(), reverse=True))
TMP_SUFFIX = ".tmp"


def cache_clear(file_name):
    if os.path.exists(file_name):
        print("cache file %s found,cleaning buffer..." % file_name)
        os.remove(file_name)
    elif os.path.exists(file_name + TMP_SUFFIX):
        print("cache file %s found,cleaning buffer..." % file_name + TMP_SUFFIX)
        os.remove(file_name + TMP_SUFFIX)
    else:
        print("cache %s not found, no need to clean..." % file_name)


def download_paper(url, dst_name):
    timeout_secs = 10  # after this many seconds we give up on a paper
    try:
        print('fetching %s into %s' % (url, dst_name))
        req = urlopen(url, None, timeout_secs)
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
                os.system('cp %s %s' % (missing_pdf_path, dst_name))
                print("could not find pdf, creating a missing pdf placeholder")
                success = True
    except Exception as e:
        print('error downloading:%s,%s' % (url, str(e)))
        cache_clear(dst_name)
        success = False
    except KeyboardInterrupt:
        print('keyboard interrupted while downloading %s' % url)
        cache_clear(dst_name)
        sys.exit()
    return success


def thread_download(db_items, start_idx, batch_size, time_max_count=100, sleep_secs=30):
    end_idx = min(start_idx + batch_size, len(db_items))
    loop = 0
    num_total = end_idx - start_idx
    num_ok = 0
    num_left = num_total
    while num_total != num_ok:
        print('starting download for %dth loop' % loop)
        time_records = []
        failed_records = []
        for idx in range(start_idx, end_idx):
            time_start = datetime.datetime.now()

            pdf_url = db_items[idx]
            basename = pdf_url.split('/')[-1]
            fname = os.path.join(Config.pdf_dir, basename)

            if download_paper(pdf_url, fname):
                num_ok += 1
                num_left -= 1
                time_take = datetime.datetime.now() - time_start
                if len(time_records) > time_max_count:
                    time_records.pop(0)
                time_records.append(time_take.seconds)
            else:
                raw_id = basename.split('v')[0]
                # arxiv add some constrain for long term download
                failed_records.append((idx, raw_id))
                if len(failed_records) > 3:
                    idx_continuous = failed_records[-1][0] == failed_records[-2][0] + 1 == failed_records[-3][0] + 2
                    same_contents = failed_records[-1][1] == failed_records[-2][1] == failed_records[-3][1]
                    if idx_continuous and not same_contents:
                        print('===============forbidden detected,sleep for %d seconds===============' % sleep_secs)
                        time.sleep(sleep_secs + random.uniform(0, 0.1))
                        failed_records = []

            print('%d/%d downloaded, %s' % (num_ok, num_total, get_left_time_str(time_records, num_left)))

        num_ok = 0
        loop += 1
        print(
            'papers downloaded okay: %d/%d, %s' % (num_ok, num_total, 'exiting' if num_ok == num_total else 'retrying'))


def get_need_download(db):
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
    db_items = get_need_download(db)
    n_threads = 1
    batch_size = len(db_items) // n_threads
    print('%d papers need to download,starting in 3 seconds...' % (len(db_items)))
    time.sleep(3)
    thread_download(db_items, 0, batch_size)
