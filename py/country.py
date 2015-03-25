import collections
from gputils import *


class Country:
    def __init__(self, row_tokens):
        self.iso = row_tokens[0].lower()
        self.iso3 = row_tokens[1].lower()
        self.fips = row_tokens[3].lower()
        self.name = row_tokens[4]
        self.population = int(row_tokens[7])
        self.tld = row_tokens[9][1:].lower()  # ".uk" -> "uk"
        self.langs = row_tokens[15].split(',')
        self.cleaned_langs = [l.lower().split('-')[0] for l in self.langs]
        self.prior = None  # Prior probability of the country generating a webpage

    def __str__(self):
        return self.name

    def __repr__(self):
        return (
            '{Country %s iso=%s, iso3=%s, fips=%s, pop=%s, tld=%s langs=%s prior=%s}' %
            (self.name, self.iso, self.iso3, self.fips, self.population, self.tld, self.cleaned_langs, self.prior)
        )

def read_countries(path_geonames=None, path_prior=None):
    if not path_geonames: path_geonames = get_data_path('geonames.txt')
    if not path_prior: path_prior = get_data_path('priors.tsv')
    iso_countries = {}

    f = gp_open(path_geonames)
    for line in f:
        if line.startswith('#'):
            continue
        c = Country(line.strip().split('\t'))
        iso_countries[c.iso] = c

    # read prior dataset
    priors = collections.defaultdict(float)
    for line in open(path_prior):
        tokens = line.strip().split('\t')
        iso = tokens[0]
        prior = float(tokens[1])
        priors[iso] = prior

    # normalize priors to sum to 1
    total = 1.0 * sum(priors.values())
    for iso in priors: priors[iso] /= total

    # allocate another 1% for smoothing across all countries, renormalize
    k = 0.01 / len(iso_countries)
    for iso in iso_countries:
        iso_countries[iso].prior = (priors[iso] + k) / 1.01

    return iso_countries.values()