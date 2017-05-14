
# arxiv sanity preserver

This project is a web interface that attempts to tame the overwhelming flood of papers on Arxiv. It allows researchers to keep track of recent papers, search for papers, sort papers by similarity to any paper, see recent popular papers, to add papers to a personal library, and to get personalized recommendations of (new or old) Arxiv papers. This code is currently running live at [www.arxiv-sanity.com/](http://www.arxiv-sanity.com/), where it's serving 25,000+ Arxiv papers from Machine Learning (cs.[CV|AI|CL|LG|NE]/stat.ML) over the last ~3 years. With this code base you could replicate the website to any of your favorite subsets of Arxiv by simply changing the categories in `fetch_papers.py`.

![user interface](https://raw.github.com/karpathy/arxiv-sanity-preserver/master/ui.jpeg)

### Code layout

There are two large parts of the code:

**Indexing code**. Uses Arxiv API to download the most recent papers in any categories you like, and then downloads all papers, extracts all text, creates tfidf vectors based on the content of each paper. This code is therefore concerned with the backend scraping and computation: building up a database of arxiv papers, calculating content vectors, creating thumbnails, computing SVMs for people, etc.

**User interface**. Then there is a web server (based on Flask/Tornado/sqlite) that allows searching through the database and filtering papers by similarity, etc.

### Dependencies

Several: You will need numpy, feedparser (to process xml files), scikit learn (for tfidf vectorizer, training of SVM), flask (for serving the results), flask_limiter, and tornado (if you want to run the flask server in production). Also dateutil, and scipy. And sqlite3 for database (accounts, library support, etc.). Most of these are easy to get through `pip`, e.g.:

```bash
$ virtualenv env                # optional: use virtualenv
$ source env/bin/activate       # optional: use virtualenv
$ pip install -r requirements.txt
```

You will also need [ImageMagick](http://www.imagemagick.org/script/index.php) and [pdftotext](https://poppler.freedesktop.org/), which you can install on Ubuntu as `sudo apt-get install imagemagick poppler-utils`. Bleh, that's a lot of dependencies isn't it.

### Processing pipeline

The processing pipeline requires you to run a series of scripts, and at this stage I really encourage you to manually inspect each script, as they may contain various inline settings you might want to change. In order, the processing pipeline is:

1. Run `fetch_papers.py` to query arxiv API and create a file `db.p` that contains all information for each paper. This script is where you would modify the **query**, indicating which parts of arxiv you'd like to use. Note that if you're trying to pull too many papers arxiv will start to rate limit you. You may have to run the script multiple times, and I recommend using the arg `--start-index` to restart where you left off when you were last interrupted by arxiv.
2. Run `download_pdfs.py`, which iterates over all papers in parsed pickle and downloads the papers into folder `pdf`
3. Run `parse_pdf_to_text.py` to export all text from pdfs to files in `txt`
4. Run `thumb_pdf.py` to export thumbnails of all pdfs to `thumb`
5. Run `analyze.py` to compute tfidf vectors for all documents based on bigrams. Saves a `tfidf.p`, `tfidf_meta.p` and `sim_dict.p` pickle files.
6. Run `buildsvm.py` to train SVMs for all users (if any), exports a pickle `user_sim.p`
7. Run `make_cache.py` for various preprocessing so that server starts faster (and make sure to run `sqlite3 as.db < schema.sql` if this is the very first time ever you're starting arxiv-sanity, which initializes an empty database).
8. Run the flask server with `serve.py`. Visit localhost:5000 and enjoy sane viewing of papers!

Optionally you can also run the `twitter_daemon.py` in a screen session, which uses your Twitter API credentials (stored in `twitter.txt`) to query Twitter periodically looking for mentions of papers in the database, and writes the results to the pickle file `twitter.p`.

I have a simple shell script that runs these commands one by one, and every day I run this script to fetch new papers, incorporate them into the database, and recompute all tfidf vectors/classifiers. More details on this process below.

**protip: numpy/BLAS**: The script `analyze.py` does quite a lot of heavy lifting with numpy. I recommend that you carefully set up your numpy to use BLAS (e.g. OpenBLAS), otherwise the computations will take a long time. With ~25,000 papers and ~5000 users the script runs in several hours on my current machine with a BLAS-linked numpy.

### Running online

If you'd like to run the flask server online (e.g. AWS) run it as `python serve.py --prod`.

You also want to create a `secret_key.txt` file and fill it with random text (see top of `serve.py`).

### Current workflow

Running the site live is not currently set up for a fully automatic plug and play operation. Instead it's a bit of a manual process and I thought I should document how I'm keeping this code alive right now. I have a script that performs the following update early morning after arxiv papers come out (~midnight PST):

```bash
python fetch_papers.py
python download_pdfs.py
python parse_pdf_to_text.py
python thumb_pdf.py
python analyze.py
python buildsvm.py
python make_cache.py
```

I run the server in a screen session, so `screen -S serve` to create it (or `-r` to reattach to it) and run:

```bash
python serve.py --prod --port 80
```

The server will load the new files and begin hosting the site. Note that on some systems you can't use port 80 without `sudo`. Your two options are to use `iptables` to reroute ports or you can use [setcap](http://stackoverflow.com/questions/413807/is-there-a-way-for-non-root-processes-to-bind-to-privileged-ports-1024-on-l) to elavate the permissions of your `python` interpreter that runs `serve.py`. In this case I'd recommend careful permissions and maybe virtualenv, etc.
