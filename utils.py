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
    pdf_dir = os.path.join('/', 'data', 'pdf')
    txt_dir = os.path.join('/', 'data', 'txt')
    thumbs_dir = os.path.join('static', 'thumbs')
    # intermediate pickles
    tfidf_path = os.path.join('/', 'data', 'pickles','tfidf.p')
    meta_path = os.path.join('/', 'data', 'pickles','tfidf_meta.p')
    sim_path = os.path.join('/', 'data', 'pickles','sim_dict.p')
    user_sim_path = os.path.join('/', 'data', 'pickles','user_sim.p')
    # sql database file
    db_serve_path = 'db2.p' # an enriched db.p with various preprocessing info
    database_path = 'as.db'
    serve_cache_path = 'serve_cache.p'
    
    beg_for_hosting_money = 1 # do we beg the active users randomly for money? 0 = no.
    banned_path = 'banned.txt' # for twitter users who are banned
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
# "0310594v1" and the dot may be missing too
def isvalidid(pid):
  return re.match('^([a-z]+(-[a-z]+)?/)?\d+(\.\d+)?(v\d+)?$', pid)



def dir_basename_from_pid(pid,j):
  """ Mapping article id from metadata to its location in the arxiv S3 tarbals. 

  Returns dir/basename without extention and without full qualified path.
  It also ignores version because there is no version in the tarbals. 
  I understand they have the updated version in the tarballs all the time.

  Add .txt .pdf or .jpg for the actual file you need and prepend with the 
  path to your files dirs.
  """
  schema="unhandled"
  if j['_rawid'][:4].isdigit() and '.' in j['_rawid']: # this is the current scheme from 0704
    schema='current' # YYMM/YYMM.xxxxx.pdf (number of xxx is variable)
    dir_basename_str = '/'.join( [ j['_rawid'][:4] , j['_rawid'] ] )
  elif '/' in j['_rawid']: # cond-mat/0210533 some rawids had the category and the id
    schema='slash' #YYMM/catYYMMxxxxx.pdf
    dir_basename_str = '/'.join( [ j['_rawid'].split("/")[1][:4], "".join(j['_rawid'].split("/")) ] )  
  else: # this is for rawid with no category, but we split category from metadata on the dot (if it has one)
    schema='else' #YYMM/catYYMMxxxxx.pdf
    dir_basename_str = '/'.join( [ j['_rawid'][:4].split("-")[0]
      , j['arxiv_primary_category']['term'].split(".")[0]+j['_rawid'] ] )
  if schema == 'unhandled':
    print('unhandled mapping in pid to tarball',j['_rawid'])
  return dir_basename_str
