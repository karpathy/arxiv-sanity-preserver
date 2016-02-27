
# arxiv sanity preserver

This project is a web interface that attempts to tame the overwhelming flood of papers on Arxiv. It allows researchers to keep track of recent papers, search for papers, sort papers by similarity to any paper, see recent popular papers, to add papers to a personal library, and to get personalized recommendations of (new or old) Arxiv papers. This code is currently running live at [www.arxiv-sanity.com/](http://www.arxiv-sanity.com/), where it's serving 15,000+ Arxiv papers from Machine Learning (cs.[CV|CL|LG|NE]/stat.ML) over the last ~3 years. I am looking for collaborators who wish to try to get this running for other parts of Arxiv as well (e.g. theory? physics?)

![user interface](https://raw.github.com/karpathy/arxiv-sanity-preserver/master/ui.jpeg)

### Code layout

There are two large parts of the code:

**Indexing code**. Uses Arxiv API to download the most recent papers in any categories you like, and then downloads all papers, extracts all text, creates tfidf vectors based on the content of each paper. This code is therefore concerned with the backend scraping and computation: building up a database of arxiv papers, calculating content vectors, creating thumbnails, computing SVMs for people, etc.

**User interface**. Then there is a web server (based on Flask/Tornado/sqlite) that allows searching through the database and filtering papers by similarity, etc.

### Dependencies

Several: You will need numpy, feedparser (to process xml files), scikit learn (for tfidf vectorizer, training of SVM), flask (for serving the results), and tornado (if you want to run the flask server in production). Also dateutil, and scipy. And sqlite3 for database (accounts, library support, etc.). Most of these are easy to get through `pip`, e.g.:

```bash
$ virtualenv env                # optional: use virtualenv
$ source env/bin/activate       # optional: use virtualenv
$ pip install -r requirements.txt
```

### Processing pipeline

Right now this project requires code reading and getting your hands dirty. I tried to keep it relatively clean, but I do encourage you to skim each script when you run it. In order, the processing pipeline is:

1. Run `fetch_papers.py` to query arxiv API and create a file `db.p` that contains all information for each paper
2. Run `download_pdf.py`, which iterates over all papers in parsed pickle and downloads the papers into folder `pdf`
3. Run `parse_pdf_to_text.py` to export all text from pdfs to files in `txt`
4. Run `thumb_pdf.py` to export thumbnails of all pdfs to `thumb`
5. Run `analyze.py` to compute tfidf vectors for all documents based on bigrams. Saves a `tfidf.p`, `tfidf_meta.p` and `sim_dict.p` pickle files.
6. Run `buildsvm.py` to train SVMs for all users (if any), exports a pickle `user_sim.p`
7. Run the flask server with `serve.py`. Visit localhost:5000 and enjoy sane viewing of papers

I have a simple shell script that runs these commands one by one, and every day I run this script to fetch new papers, incorporate them into the database, and recompute all tfidf vectors/classifiers.

### Running online

If you'd like to run this flask server online (e.g. AWS) run it as `python serve.py --prod`. 

You also want to create a `secret_key.txt` file and fill it with random text (see top of `serve.py`).
