
# arxiv sanity preserver

There are way too many arxiv papers, so I wrote a quick webapp that lets you search and sort through the mess in a pretty interface, similar to my [pretty conference format](http://cs.stanford.edu/people/karpathy/nips2014/).

It's super hacky and was written in 4 hours. I'll keep polishing it a bit over time perhaps but it serves its purpose for me already. 

Main functionality is a search feature, and most useful is that you can click "sort by tfidf similarity to this", which returns all the most similar papers to that one in terms of tfidf bigrams. I find this quite useful.

![user interface](https://raw.github.com/karpathy/arxiv-sanity-preserver/master/ui.jpeg)

### Dependencies
You will need numpy, scikit learn (for tfidf vectorizer), and flask (for serving the results)

### Ugly I don't have time processing pipeline

Requires reading code and getting hands dirty. Magic numbers throughout code.

1. Run `scrape.py`, which queries most recent papers in Arxiv and dumps xml into folder `raw`
2. Run `parse_raw.py`, which reads all xml files in `raw` and creates a pickle with all critical information called `db.p`.
3. Run `download_pdf.py`, which iterates over all papers in parsed pickle and downloads the papers into folder `pdf`
4. Run `parse_pdf_to_text.py` to export all text from pdfs to files in `txt`
5. Run `analyze.py` to compute tfidf vectors for all documents based on bigrams. Saves a `tfidf.p` pickle file.
6. Run `thumb_pdf.py` to export thumbnails of all pdfs to `thumb`
7. Run the flask server with `serve.py`. Visit localhost:5000 and enjoy sane viewing of papers

### Prebuilt database

If you'd like to browse arxiv papers from last 3 months you can download the result of running the above steps 1-6, and only run 7. to browse. [Here is the download link.](cs.stanford.edu/people/karpathy/arxiv_cv_lg_sep_to_dec.zip). Unzip in root folder and fire up flask with `serve.py`. Should work I think.



