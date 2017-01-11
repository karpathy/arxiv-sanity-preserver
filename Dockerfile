FROM python:2

RUN apt-get update -y && apt-get install -y poppler-utils imagemagick libopenblas-dev ghostscript sqlite3 sudo

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /usr/src/app

RUN mkdir -p /usr/src/app/data
RUN ln -s data/txt data/pdf data/db.p data/tfidf_meta.p data/sim_dict.p data/user_sim.p data/tfidf.p data/search_dict.p data/as.db data/tmp data/secret_key.txt . && ln -s ../data/thumbs static/

EXPOSE 8080

ENTRYPOINT ["./docker.sh"]
CMD ["python", "serve.py", "--prod", "--port", "8080"]
