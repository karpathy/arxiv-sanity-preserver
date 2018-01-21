scholar.py
==========

scholar.py is a Python module that implements a querier and parser for Google Scholar's output. Its classes can be used independently, but it can also be invoked as a command-line tool.

The script used to live at http://icir.org/christian/scholar.html, and I've moved it here so I can more easily manage the various patches and suggestions I'm receiving for scholar.py. Thanks guys, for all your interest! If you'd like to get in touch, email me at christian@icir.org or ping me [on Twitter](http://twitter.com/ckreibich).

Cheers,<br>
Christian

Features
--------

* Extracts publication title, most relevant web link, PDF link, number of citations, number of online versions, link to Google Scholar's article cluster for the work, Google Scholar's cluster of all works referencing the publication, and excerpt of content.
* Extracts total number of hits as reported by Scholar (new in version 2.5)
* Supports the full range of advanced query options provided by Google Scholar, such as title-only search, publication date timeframes, and inclusion/exclusion of patents and citations.
* Supports article cluster IDs, i.e., information relating to the variants of an article already identified by Google Scholar
* Supports retrieval of citation details in standard external formats as provided by Google Scholar, including BibTeX and EndNote.
* Command-line tool prints entries in CSV format, simple plain text, or in the citation export format.
* Cookie support for higher query volume, including ability to persist cookies to disk across invocations.

Note
----

I will always strive to add features that increase the power of this
API, but I will never add features that intentionally try to work
around the query limits imposed by Google Scholar. Please don't ask me
to add such features.

Examples
--------

Try scholar.py --help for all available options. Note, the command line arguments changed considerably in version 2.0! A few examples:

Retrieve one article written by Einstein on quantum theory:

    $ scholar.py -c 1 --author "albert einstein" --phrase "quantum theory"
             Title On the quantum theory of radiation
               URL http://icole.mut-es.ac.ir/downloads/Sci_Sec/W1/Einstein%201917.pdf
              Year 1917
         Citations 184
          Versions 3
        Cluster ID 17749203648027613321
          PDF link http://icole.mut-es.ac.ir/downloads/Sci_Sec/W1/Einstein%201917.pdf
    Citations list http://scholar.google.com/scholar?cites=17749203648027613321&as_sdt=2005&sciodt=0,5&hl=en
     Versions list http://scholar.google.com/scholar?cluster=17749203648027613321&hl=en&as_sdt=0,5
           Excerpt The formal similarity between the chromatic distribution curve for thermal radiation [...]


Note the cluster ID in the above. Using this ID, you can directly access the cluster of articles Google Scholar has already determined to be variants of the same paper. So, let's see the versions:

    $ scholar.py -C 17749203648027613321
             Title On the quantum theory of radiation
               URL http://icole.mut-es.ac.ir/downloads/Sci_Sec/W1/Einstein%201917.pdf
         Citations 184
          Versions 0
        Cluster ID 17749203648027613321
          PDF link http://icole.mut-es.ac.ir/downloads/Sci_Sec/W1/Einstein%201917.pdf
    Citations list http://scholar.google.com/scholar?cites=17749203648027613321&as_sdt=2005&sciodt=0,5&hl=en
           Excerpt The formal similarity between the chromatic distribution curve for thermal radiation [...]

             Title ON THE QUANTUM THEORY OF RADIATION
               URL http://www.informationphilosopher.com/solutions/scientists/einstein/1917_Radiation.pdf
         Citations 0
          Versions 0
          PDF link http://www.informationphilosopher.com/solutions/scientists/einstein/1917_Radiation.pdf
           Excerpt The formal similarity between the chromatic distribution curve for thermal radiation [...]
    
             Title The Quantum Theory of Radiation
               URL http://web.ihep.su/dbserv/compas/src/einstein17/eng.pdf
         Citations 0
          Versions 0
          PDF link http://web.ihep.su/dbserv/compas/src/einstein17/eng.pdf
           Excerpt 1 on the assumption that there are discrete elements of energy, from which quantum [...]


Let's retrieve a BibTeX entry for that quantum theory paper. The best BibTeX often seems to be the one linked from search results, not those in the article cluster, so let's do a search again:

    $ scholar.py -c 1 --author "albert einstein" --phrase "quantum theory" --citation bt
    @article{einstein1917quantum,
      title={On the quantum theory of radiation},
      author={Einstein, Albert},
      journal={Phys. Z},
      volume={18},
      pages={121--128},
      year={1917}
    }

Report the total number of articles Google Scholar has for Einstein:

    $ scholar.py --txt-globals --author "albert einstein" | grep '\[G\]' | grep Results
    [G]    Results 4190


License
-------

scholar.py is using the standard [BSD license](http://opensource.org/licenses/BSD-2-Clause).
