# Geo-provenance

This project contains tools for inferring the *geoprovenance* of webresources.
A web page's geoprovenance is the home country for the original publisher of the information contained in the web page.

The geoprovenance of:
* A web resource created by a company or organization is the country where its headquarters are located.
* A web resource created by an individual author is that individual's home country.
* A book is the country associated with the publisher of the book.
* More details are provided in our [2015 CHI paper](http://www-users.cs.umn.edu/~bhecht/publications/localnessgeography_CHI2015.pdf). 

If you use this software in an academic publication, please cite it as follows: Sen, S., Ford, H., Musicant, D., Graham, M., Keyes, O., and Hecht, B. 2015. "[Barriers to the Localness of Volunteered Geographic Information](http://www-users.cs.umn.edu/~bhecht/publications/localnessgeography_CHI2015.pdf)." *Proceedings of CHI 2015.* New York: ACM Press.

There are a few deviations from the published algorithm (TODO fix these):
* Does not follow links to `archive.org` and other repositories.
* Does not handle binary files, like PDFs, Open Office docs, and Microsoft docs.
* Not integrated with amazon web services to scrape en-mass.

### Installing necessary Python modules:

```bash
pip install tldextract
pip install chardet
pip install geopy
pip install beautifulsoup4
pip install langid
```

If you want to run the evaluator, which rebuilds the logistic regression (not necessary to use the pre-built model), you'll also need to install `sklearn`.

### Running the command-line program.

The `py` directory contains the `run_inferrer.py` program, which reads URLs from standard input and writes information about them to standard output. For example, if you ran the following from the shell from within the `py` directory:

```bash
$ echo 'http://www.timeout.com/dublin/' | python ./run_inferrer.py
```

You would see the following output:

```text
http://www.timeout.com/dublin/  gb      0.8259  {'gb' : 0.8259, 'us' : 0.0628, 'fr' : 0.0008, 'ca' : 0.0006, 'ru' : 0.0006, 'in' : 0.0005, 'de' : 0.0005, 'se' : 0.0005, 'it' : 0.0005, 'pl' : 0.0005}
```

run_inferrer.py outputs the following four tab-separated fields: 

1. The URL itself.
2. The most probable country.
3. The estimated probability the most probable country is correct (in this case, about 83%).
4. The top 10 candidate countries, along with their associated probabilities, in JSON format.

If you run the program from somewhere outside of the `py` directory, or would like to use a larger pre-built feature cache (see information below), you can specify the feature directory, or both the features and data directories, from the command line:

```bash
$ python run_inferrer.py path/to/features/dir
$ python run_inferrer.py path/to/features/dir path/to/data/dir
```

### Incorporating the module into your own Python program.

```python
import gputils
import gpinfer

# necessary iff not run from the "py" directory
gputils.set_data_dir('/path/to/data')

# necessary iff not run from the "py" directory or alternate feature caches are used (see below)
gputils.set_feature_dir('/path/to/feature')

inferrer = gpinfer.LogisticInferrer()

# conf is a number between 0 and 1.0 indicating confidence
# dist is a dict with keys country codes and values predicted probability
(conf, dist) = inferrer.infer('http://www.timeout.com/dublin/')
```

### Incorporating larger pre-built caches for speed

A larger feature cache is available at https://www.dropbox.com/s/hq5ogzrd2jobwwh/geo-provenance-features.zip?dl=0. To use this feature cache, download and extract the zip file. You'll then need to point the module at the feature directory by either specifying the appropriate argument to the run_inferrer.py program, or by calling `gp_utils.set_feature_dir` with the appropriate absolute pathname.

This cache contains information about all 7.5M URLs analyzed in our CHI paper.

### The GeoProv198 Dataset

The logistic regression classification model used in this package is trained using a gold standard dataset that maps urls to countries. This dataset is available in the [data](https://github.com/shilad/geo-provenance/blob/master/data/geoprov198.tsv) directory and its collection methodology is described in the citation above.

### Credits

* Shilad Sen developed the geoprovenance inference algorithm and software.
* Dave Musicant developed the original Ruby code to extract country names from whois queries.
* Heather Ford led development of GeoProv198, with major assistance from Brent Hecht and minor assistance from Dave Musicant, Shilad Sen, and Mark Graham.
* Matthew Zook provided some early guidance on the design of our algorithm.
