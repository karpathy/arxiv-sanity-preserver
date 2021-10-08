"""
Queries arxiv API and downloads papers (the query is a parameter).
The script is intended to enrich an existing database pickle (by default db.p),
so this file will be loaded first, and then new results will be added to it.
"""
import argparse
import time
import random
import urllib.request

import feedparser

from utils import Config, safe_pickle_dump, to_int_time, separate_by_month, to_datetime, several_days_around, load_db, \
    is_first_day_of_month, several_months_around, PAPER_INIT_YEAR


def encode_feedparser_dict(d):
    if isinstance(d, feedparser.FeedParserDict) or isinstance(d, dict):
        j = {}
        for k in d.keys():
            j[k] = encode_feedparser_dict(d[k])
        return j
    elif isinstance(d, list):
        l = []
        for k in d:
            l.append(encode_feedparser_dict(k))
        return l
    else:
        return d


def parse_arxiv_url(url):
    ix = url.rfind('/')
    idversion = url[ix + 1:]  # extract just the id (and the version)
    parts = idversion.split('v')
    assert len(parts) == 2, 'error parsing url ' + url
    return parts[0], int(parts[1])


def get_time(last_updated_time):
    last_updated_time = to_int_time(last_updated_time)
    current_time = to_int_time(time.localtime())
    time_start = []
    time_start.append(last_updated_time)
    if last_updated_time < 20090101000000:
        time_start.append(20090101000000)
    if last_updated_time < 20120101000000:
        time_start.append(20120101000000)
    if last_updated_time < 20150101000000:
        while time_start[-1] < 20150101000000:
            time_start.append(time_start[-1] + 10000000000)
    if last_updated_time < 20170101000000:
        time_start += separate_by_month(time_start[-1], 20170101000000, 6)
    if last_updated_time < 20180101000000:
        time_start += separate_by_month(time_start[-1], 20180101000000, 3)
    if last_updated_time < 20190101000000:
        time_start += separate_by_month(time_start[-1], 20190101000000, 2)
    if last_updated_time < 20210101000000:
        time_start += separate_by_month(time_start[-1], 20210101000000, 1)
    if last_updated_time < 20990101000000:
        loop_start = to_datetime(time_start[-1])
        loop_end = to_datetime(current_time)
        loop_start = several_days_around(loop_start, 15)

        while loop_start <= loop_end:
            time_start.append(to_int_time(loop_start))
            loop_start = several_days_around(loop_start, 15)
    time_end = time_start[1:]
    time_end.append(current_time)
    return time_start, time_end


def query(time_start, time_end, start_idx: int, max_len: int, type):
    timeout_secs = 120  # after this many seconds we give up on a paper
    time_start = str(to_int_time(time_start))
    time_end = str(to_int_time(time_end))
    type = 'lastUpdatedDate' if type == 'last_updated' else 'submittedDate'
    base_url = 'http://export.arxiv.org/api/query?'
    default_categories = '%28cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:cs.CY+OR+cat:cs.LG+OR+cat:cs.NE+OR+cat:cs.SD+OR+cat:eess.AS+OR+cat:eess.IV+OR+cat:eess.SP+OR+cat:eess.SY+OR+cat:stat.ML%29'
    default_query = 'search_query=%s+AND+' + type + ':[' + time_start + '+TO+' + time_end + ']&sortBy=' + type + '&sortOrder=descending&start=%i&max_results=%i'

    with urllib.request.urlopen(base_url + (default_query % (default_categories, start_idx, max_len)),
                                timeout=timeout_secs) as url:
        response = url.read()
    parsed = feedparser.parse(response)
    info, result = parsed.feed, parsed.entries
    return info, result


def db_get_last_time(db, query_order_by):
    parse_type = 'updated_parsed' if query_order_by == 'last_updated' else 'published_parsed'
    max_date = PAPER_INIT_YEAR

    for i, k in enumerate(db):
        tm_int = to_int_time(db[k][parse_type])
        max_date = tm_int if tm_int > max_date else max_date

    # minus 10 days for api uncertainty
    max_date = several_days_around(to_datetime(max_date), 10, False)

    return max_date


def update_data(db, expected_count, query_result):
    num_added = 0
    num_updated = 0
    num_skipped = 0
    for e in query_result:

        j = encode_feedparser_dict(e)

        # extract just the raw arxiv id and version for this paper
        rawid, version = parse_arxiv_url(j['id'])
        j['_rawid'] = rawid
        j['_version'] = version

        # add to our database if we didn't have it before, or if this is a new version
        if rawid not in db:
            db[rawid] = j
            print('Add %s %s' % (j['updated'].encode('utf-8'), j['title'].encode('utf-8')))
            num_added += 1
        elif j['_version'] > db[rawid]['_version']:
            db[rawid] = j
            print('Update %s %s' % (j['updated'].encode('utf-8'), j['title'].encode('utf-8')))
            num_updated += 1
        else:
            num_skipped += 1

    total = num_added + num_updated + num_skipped
    # print some information
    print('expected:%d, Added %d papers,Updated %d papers, already had %d, total %d' % (
        expected_count, num_added, num_updated, num_skipped, total))

    # save the database before we quit, if we found anything new
    if num_added > 0 or num_updated > 0:
        print('Saving database with %d papers to %s' % (len(db), Config.db_path))
        safe_pickle_dump(db, Config.db_path)

    return total


def fetching_papers(start_arr, end_arr, db, query_order_by):
    wait_time = 0.5  # query need min wait seconds
    first_start = True
    while first_start or len(start_arr) > 0:
        wrong_download_start, wrong_download_end = [], []

        for i in range(len(start_arr)):
            max_index = -1
            try:
                info, _ = query(start_arr[i], end_arr[i], 0, 1, query_order_by)
                max_index = int(info.opensearch_totalresults)

                print('year:%d → %d, exp:%d, start downloading...' % (start_arr[i], end_arr[i], max_index))
                _, result = query(start_arr[i], end_arr[i], 0, max_index + 1, query_order_by)
                total = update_data(db, max_index, result)
            except Exception as e:
                print('error downloading:%d,%s' % (start_arr[i], str(e)))
                total = 0

            if total != max_index:
                wrong_download_start.append(start_arr[i])
                wrong_download_end.append(end_arr[i])

            time_sleep = wait_time + random.uniform(0, 3)
            print('Sleeping for %f seconds' % (time_sleep))
            time.sleep(time_sleep)

        first_start = False
        print('start time %s data count mismatch, corresponding end time %s, %s' % (
            str(wrong_download_start), str(wrong_download_end),
            'retrying...' if len(wrong_download_start) > 0 else 'exiting...'))
        start_arr, end_arr = wrong_download_start, wrong_download_end


if __name__ == "__main__":

    # parse input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait', type=float, default=5.0,
                        help='query need min wait seconds (in number of seconds)')
    args = parser.parse_args()

    db = load_db(Config.db_path)

    # ordinary sync every day,sync 10 days before last paper updated date
    last_updated_time = db_get_last_time(db, 'last_updated')
    time_start, time_end = get_time(last_updated_time)
    print('Fetching last 10 days data')
    fetching_papers(time_start, time_end, db, 'last_updated')

    if is_first_day_of_month():
        # sync every month tracking last 3 months published data because of arxiv data error
        time_start, time_end = get_time(several_months_around(last_updated_time, 3, False))
        print('First day of month,fetching all published data')
        fetching_papers(time_start, time_end, db, 'published')
