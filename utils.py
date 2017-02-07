from contextlib import contextmanager

import os
import re
import pickle
import tempfile

# global settings
# -----------------------------------------------------------------------------
class Config(object):
    # main paper information repo file
    db_path = 'db.p'
    # intermediate processing folders
    pdf_dir = os.path.join('data', 'pdf')
    txt_dir = os.path.join('data', 'txt')
    thumbs_dir = os.path.join('static', 'thumbs')
    # intermediate pickles
    tfidf_path = 'tfidf.p'
    meta_path = 'tfidf_meta.p'
    sim_path = 'sim_dict.p'
    user_sim_path = 'user_sim.p'
    tweet_path = 'twitter.p' # written by twitter_daemon.py
    # sql database file
    database_path = 'as.db'
    search_dict_path = 'search_dict.p'
    
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
                os.fsync(file.fileno())
        os.rename(tmppath, filepath)

def safe_pickle_dump(obj, fname):
    with open_atomic(fname, 'wb') as f:
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
