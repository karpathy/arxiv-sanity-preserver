import wikipedia
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer,CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

from utils import Config, safe_pickle_dump

lda=pickle.load(open('./ldamodel.p', 'rb'))
nlp=wikipedia.page('Natural-language_processing')

title=nlp.title
contents=nlp.content.split('\n')

tf_vectorizer = TfidfVectorizer(
            input='content',
            encoding='utf-8',
            strip_accents='unicode',
            decode_error='replace',
            lowercase=True,
            analyzer='word',
            token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',
            ngram_range=(1,2),
            max_df=0.95, min_df=1,
            stop_words='english',
            max_features=1000,
            norm='l2',
            use_idf=True,
            smooth_idf=True,
            sublinear_tf=True
            )
tf = tf_vectorizer.fit_transform(contents)
docs=lda.transform(tf)

print(docs)