FROM python
RUN    apt-get update \
    && apt-get install -y nano imagemagick ghostscript poppler-utils sqlite3 libsqlite3-dev
ADD . /code
WORKDIR /code
RUN pip install -r requirements.txt
