import wikipedia
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer,CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

from utils import Config, safe_pickle_dump

lda=pickle.load(open('./ldamodel.p', 'rb'))
nlp=wikipedia.page('Natural-language_processing')

title=nlp.title
contents=nlp.content.lower().split('\n')

tf_vectorizer = CountVectorizer(strip_accents='unicode',
                                decode_error='replace',
                                analyzer='word',
                                token_pattern=r'\b[a-zA-Z]{3,}\b',
                                max_df=0.95, min_df=2,
                                stop_words='english',
                                max_features=1000
                                )
tf = tf_vectorizer.fit_transform(contents)
docs=lda.fit_transform(tf)

print(docs.shape)