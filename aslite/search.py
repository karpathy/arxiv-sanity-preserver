"""
Keyword search over papers, with a small query language:

    diffusion                plain term, matched as a whole word (so "rl" won't match "world"),
                             plurals match too (network -> networks)
    "graph neural network"   exact phrase (punctuation/whitespace between words is flexible)
    learn*                   prefix wildcard: learn, learning, learned, ...
    +robotics                required: papers without it are dropped
    -survey                  excluded: papers with it are dropped
    au:hinton                restrict to a field: au (authors), ti (title), abs (abstract)

Prefixes combine, e.g. +au:"yann lecun" or -ti:survey.
Matching is case and accent insensitive (Schölkopf == scholkopf).
"""

import re
import unicodedata

# score weights per field, per matched term
FIELD_WEIGHTS = {'au': 10.0, 'ti': 20.0, 'abs': 1.0}
ALL_FIELDS = tuple(FIELD_WEIGHTS.keys())
FIELD_ALIASES = {
    'au': 'au', 'author': 'au', 'authors': 'au',
    'ti': 'ti', 'title': 'ti',
    'abs': 'abs', 'abstract': 'abs',
}
MAX_ABS_COUNT = 3 # cap on how many abstract occurrences of one term count towards the score

# one token: optional +/-, optional field:, then either "a phrase" or a bare word
TOKEN_RE = re.compile(r'([+-]?)(?:(\w+):)?(?:"([^"]*)"?|(\S+))')

def normalize(s):
    """ lowercase and strip accents """
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.lower()

def _make_pattern(words, prefix):
    parts = [re.escape(w) for w in words]
    body = r'\W+'.join(parts) # tolerate hyphens, newlines, double spaces between phrase words
    tail = r'\w*' if prefix else r'(?:e?s)?(?!\w)' # allow a plural ending on the last word
    return re.compile(r'(?<!\w)' + body + tail)

def parse_query(q):
    """
    parses the raw query string into a list of terms, each a dict with
    keys: mod ('' | '+' | '-'), fields (tuple), pattern (compiled regex), nwords (int)
    """
    terms = []
    for m in TOKEN_RE.finditer(normalize(q)):
        mod, field, phrase, word = m.groups()
        fields = ALL_FIELDS
        if field is not None:
            if field in FIELD_ALIASES:
                fields = (FIELD_ALIASES[field],)
            else:
                # not a field we know, e.g. "cs:..." -> treat the whole thing as a word
                word = field + ':' + (word if word is not None else phrase)
                phrase = None
        text = phrase if phrase is not None else word
        prefix = phrase is None and text.endswith('*')
        words = re.findall(r'\w+', text)
        if not words:
            continue # e.g. a lone "-" or "*" or empty quotes
        terms.append({
            'mod': mod,
            'fields': fields,
            'pattern': _make_pattern(words, prefix),
            'nwords': len(words),
        })
    return terms

def paper_fields(p):
    """ extracts the normalized searchable text fields of a paper """
    return {
        'au': normalize(', '.join(a['name'] for a in p['authors'])),
        'ti': normalize(p['title']),
        'abs': normalize(p['summary']),
    }

def score_paper(terms, fields):
    """
    returns the score of a paper given parsed query terms and its paper_fields,
    or None if the paper fails a required (+) or excluded (-) term
    """
    score = 0.0
    for t in terms:
        tscore = 0.0
        for f in t['fields']:
            if f == 'abs':
                n = min(MAX_ABS_COUNT, len(t['pattern'].findall(fields[f])))
            else:
                n = 1 if t['pattern'].search(fields[f]) else 0
            tscore += FIELD_WEIGHTS[f] * n
        if t['mod'] == '-' and tscore > 0:
            return None
        if t['mod'] == '+' and tscore == 0:
            return None
        if t['mod'] != '-':
            score += tscore * t['nwords'] # longer phrases are more specific, reward them
    return score

def search(q, pdb):
    """ searches the papers dict-like pdb, returns (pids, scores) sorted by descending score """
    terms = parse_query(q)
    if not any(t['mod'] != '-' for t in terms):
        return [], [] # no positive terms? no results
    pairs = []
    for pid, p in pdb.items():
        score = score_paper(terms, paper_fields(p))
        if score:
            pairs.append((score, pid))
    pairs.sort(reverse=True)
    pids = [p[1] for p in pairs]
    scores = [p[0] for p in pairs]
    return pids, scores
