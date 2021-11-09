import datetime
import time
from contextlib import contextmanager

import os
import re
import pickle
import tempfile

# global settings
# -----------------------------------------------------------------------------
from dateutil.relativedelta import relativedelta


class Config(object):
    # main paper information repo file
    db_path = 'db.p'
    # intermediate processing folders
    pdf_dir = os.path.join('data', 'pdf')
    thumbs_dir = os.path.join('static', 'thumbs')
    # intermediate pickles
    tfidf_path = 'tfidf.p'
    meta_path = 'tfidf_meta.p'
    sim_path = 'sim_dict.p'
    user_sim_path = 'user_sim.p'
    # sql database file
    db_serve_path = 'db2.p'  # an enriched db.p with various preprocessing info
    database_path = 'as.db'
    serve_cache_path = 'serve_cache.p'

    beg_for_hosting_money = 1  # do we beg the active users randomly for money? 0 = no.
    banned_path = 'banned.txt'  # for twitter users who are banned
    tmp_dir = 'tmp'


# Context managers for atomic writes courtesy of
# http://stackoverflow.com/questions/2333872/atomic-writing-to-file-with-python
@contextmanager
def _tempfile(*args, **kws):
    """ Context for temporary file.

    Will find a free temporary filename upon entering
    and will try to delete the file on leaving

    Parameters
    ----------
    suffix : string
        optional file suffix
    """

    fd, name = tempfile.mkstemp(*args, **kws)
    os.close(fd)
    try:
        yield name
    finally:
        try:
            os.remove(name)
        except OSError as e:
            if e.errno == 2:
                pass
            else:
                raise e


@contextmanager
def open_atomic(filepath, *args, **kwargs):
    """ Open temporary file object that atomically moves to destination upon
    exiting.

    Allows reading and writing to and from the same filename.

    Parameters
    ----------
    filepath : string
        the file path to be opened
    fsync : bool
        whether to force write the file to disk
    kwargs : mixed
        Any valid keyword arguments for :code:`open`
    """
    fsync = kwargs.pop('fsync', False)

    with _tempfile(dir=os.path.dirname(filepath)) as tmppath:
        with open(tmppath, *args, **kwargs) as f:
            yield f
            if fsync:
                f.flush()
                os.fsync(f.fileno())
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(tmppath, filepath)


def safe_pickle_dump(obj, fname):
    with open_atomic(fname, 'wb', fsync=True) as f:
        pickle.dump(obj, f, -1)


# arxiv utils
# -----------------------------------------------------------------------------

def strip_version(idstr):
    """ identity function if arxiv id has no version, otherwise strips it. """
    parts = idstr.split('v')
    return parts[0]


# "1511.08198v1" is an example of a valid arxiv id that we accept
def isvalidid(pid):
    return re.match('^\d+\.\d+(v\d+)?$', pid)


# time utils
# -----------------------------------------------------------------------------

DEFAULT_TIME_FORMAT = '%Y%m%d%H%M%S'
PAPER_INIT_YEAR = 19900101000000


def add_zero(num: int):
    return str(num) if num > 9 else '0' + str(num)


def is_first_day_of_month():
    current_struct_time = time.localtime()
    return current_struct_time.tm_mday == 1


def is_first_day_of_half_year():
    current_struct_time = time.localtime()
    return current_struct_time.tm_mday == 1 and (current_struct_time.tm_mon == 1 or current_struct_time.tm_mon == 7)


def several_months_around(anchor, months: int, is_raise=True):
    anchor = to_datetime(anchor)
    if is_raise:
        anchor = anchor + relativedelta(months=months)
    else:
        anchor = anchor - relativedelta(months=months)
    return anchor


def several_days_around(anchor, days: int, is_raise=True):
    anchor = to_datetime(anchor)
    if is_raise:
        anchor = anchor + relativedelta(days=days)
    else:
        anchor = anchor - relativedelta(days=days)
    return anchor


def to_int_time(obj):
    if isinstance(obj, float):
        return int(datetime.datetime.fromtimestamp(obj).strftime(DEFAULT_TIME_FORMAT))
    elif isinstance(obj, datetime.datetime):
        return int(datetime.datetime.strftime(obj, DEFAULT_TIME_FORMAT))
    elif isinstance(obj, time.struct_time):
        yr = obj.tm_year
        mn = add_zero(obj.tm_mon)
        dy = add_zero(obj.tm_mday)
        dh = add_zero(obj.tm_hour)
        dm = add_zero(obj.tm_min)
        ds = add_zero(obj.tm_sec)
        return int(str(yr) + mn + dy + dh + dm + ds)
    elif isinstance(obj, int):
        return obj
    else:
        raise NotImplementedError('convert to int time failed:type unsupported')


def to_datetime(obj):
    if isinstance(obj, float):
        return datetime.datetime.fromtimestamp(obj)
    elif isinstance(obj, int) or isinstance(obj, str):
        return datetime.datetime.strptime(str(obj), DEFAULT_TIME_FORMAT)
    elif isinstance(obj, time.struct_time):
        return datetime.datetime.strptime(str(to_int_time(obj)), DEFAULT_TIME_FORMAT)
    elif isinstance(obj, datetime.datetime):
        return obj
    else:
        raise NotImplementedError('convert to datetime failed:type unsupported')


def to_struct_time(obj):
    if isinstance(obj, float):
        return datetime.datetime.fromtimestamp(obj).timetuple()
    elif isinstance(obj, int) or isinstance(obj, str):
        return datetime.datetime.strptime(str(obj), DEFAULT_TIME_FORMAT).timetuple()
    elif isinstance(obj, datetime.datetime):
        return obj.timetuple()
    elif isinstance(obj, time.struct_time):
        return obj
    else:
        raise NotImplementedError('convert to struct time failed:type unsupported')


def time_diff_in_seconds(src_time, tgt_time):
    src_time = to_datetime(src_time)
    tgt_time = to_datetime(tgt_time)
    if src_time > tgt_time:
        delta = src_time - tgt_time
    else:
        delta = tgt_time - src_time
    return delta.days * 24 * 3600


def separate_by_month(start, end, month):
    result = []
    loop_start = to_datetime(start)
    loop_end = to_datetime(end)
    loop_start = several_months_around(loop_start, month)

    while loop_start <= loop_end:
        result.append(to_int_time(loop_start))
        loop_start = several_months_around(loop_start, month)

    return result


def get_left_time_str(history_take_seconds, remain_counts):
    if remain_counts == 0:
        return "completed!"
    remain_seconds = sum(history_take_seconds) / len(history_take_seconds) * remain_counts
    remain_days, remain_seconds = remain_seconds // 86400, remain_seconds % 86400
    remain_hours, remain_seconds = remain_seconds // 3600, remain_seconds % 3600
    remain_minutes, remain_seconds = remain_seconds // 60, remain_seconds % 60
    return 'will take another %s%d:%d:%d to finish' % ('' if remain_days == 0 else str(int(remain_days)) + ' days ',
                                                       remain_hours, remain_minutes, remain_seconds)


# db utils
# -----------------------------------------------------------------------------


def load_db(db_path, init_db_content=None):
    # main loop where we fetch the new results
    print('loading database:%s' % db_path)
    # lets load the existing database to memory
    if init_db_content is None:
        init_db_content = {}
    try:
        db = pickle.load(open(db_path, 'rb'))
        print('db len %d' % len(db))
    except Exception as e:
        print('error loading existing database:')
        print(e)
        print('starting from an empty database')
        db = init_db_content

    return db
