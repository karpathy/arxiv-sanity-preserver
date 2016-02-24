
# arxiv sanity preserver

There are way too many arxiv papers, so I wrote a quick webapp that lets you search and sort through the mess in a pretty interface, similar to my [pretty conference format](http://cs.stanford.edu/people/karpathy/nips2014/). The code is broken up into two main pieces:

**Indexing code**. Uses Arxiv API to download the most recent papers in any categories you like, and then downloads all papers, extracts all text, and creates tfidf vectors for each paper. This code is therefore concerned with building up a database of arxiv papers, calculating content vectors, creating thumbnails, etc.

**User interface**. Then there is a web server (based on Flask) that enables searching through the database and filtering papers by similarity, etc. Main functionality is a search feature, and most useful is that you can click "sort by tfidf similarity to this", which returns all the most similar papers to that one in terms of tfidf bigrams. I find this quite useful.

![user interface](https://raw.github.com/karpathy/arxiv-sanity-preserver/master/ui.jpeg)

### Find it online

This code is currently running live at [www.arxiv-sanity.com/](http://www.arxiv-sanity.com/). Right now it's serving ~13,000 arxiv papers from cs.[CV|CL|LG] over the last ~3 years, and more will be added in time as I build this out.

### Dependencies
You will need numpy, feedparser (to process xml files), scikit learn (for tfidf vectorizer), and flask (for serving the results), and tornado (if you want to run the flask server in production). Also dateutil, and scipy. And sqlite3 for database (accounts, library support, etc.). Most of these are easy to get through `pip`, e.g.:

```bash
$ virtualenv env                # optional: use virtualenv
$ source env/bin/activate       # optional: use virtualenv
$ pip install feedparser        # only if you want to scrape arxiv
$ pip install numpy             
$ pip install scipy             
$ pip install scikit-learn      # needed for sparse arrays
$ pip install python-dateutil   # only in serve.py for some date utils
$ pip install flask             # only in serve.py
$ pip install tornado           # only in serve.py
$ pip install sqlite3           # only in serve.py
```

### Processing pipeline

Right now this code requires reading code and getting your hands dirty. There are a few magic numbers throughout code, but luckily each script is quite short, transparent and easy to modify. In order there are:

1. Run `fetch_papers.py` to query arxiv API and create a file `db.p` that contains all information for each paper
2. Run `download_pdf.py`, which iterates over all papers in parsed pickle and downloads the papers into folder `pdf`
3. Run `parse_pdf_to_text.py` to export all text from pdfs to files in `txt`
4. Run `thumb_pdf.py` to export thumbnails of all pdfs to `thumb`
5. Run `analyze.py` to compute tfidf vectors for all documents based on bigrams. Saves a `tfidf.p`, `tfidf_meta.p` and `sim_dict.p` pickle files.
6. Run `buildsvm.py` to train SVMs for all users (if any)
6. Run the flask server with `serve.py`. Visit localhost:5000 and enjoy sane viewing of papers

### Running online

If you'd like to run this flask server online (e.g. AWS/Terminal) run it as `python serve.py --prod`.

The interface supports a simple creation of user accounts. A logged in user can save papers into their library, and view them later. 

In a later release we will actually build a custom SVM for each user based on the list of papers in their library.
