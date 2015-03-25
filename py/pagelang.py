import collections
import os

from gputils import *

import country


class PagelangProvider:
    def __init__(self, path=None):
        if not path: path = get_feature_data_path('pagelangs')
        if not os.path.isfile(path):
            raise GPException('page language results not available...')

        warn('reading pagelang results...')
        nlines = 0
        self.pagelangs = {}
        for line in gp_open(path):
            tokens = line.strip().split('\t')
            if len(tokens) == 2:
                url = tokens[0]
                cc = tokens[1]
                if cc != 'unknown':
                    self.pagelangs[url] = cc
                nlines += 1
            else:
                warn('invalid pagelang line: %s' % `line`)
        warn('finished reading %d pagelang entries' % nlines)

    def get(self, url):
        return self.pagelangs[url]

    def contains(self, url):
        return url in self.pagelangs


class CountrylangProvider:
    def __init__(self, countries=None):
        if not countries:
            countries = country.read_countries()
        iso_countries = dict([(c.iso, c) for c in countries])

        total_pop = sum([c.population for c in countries])

        # calculate language to country mapping
        lang2countries = collections.defaultdict(list)
        for c in iso_countries.values():
            for (i, l) in enumerate(c.cleaned_langs):
                p = 1.0 * c.population / total_pop
                s = p * 1.0 / ((i+1) ** 2.5)
                lang2countries[l].append((s, c.iso))

        self.lang_countries = {}
        for lang, country_scores in lang2countries.items():
            country_scores.sort()
            country_scores.reverse()
            sum_scores = 1.0 * sum([s for (s, c) in country_scores]) + 0.000001
            self.lang_countries[lang] = [(c, score/sum_scores) for (score, c) in country_scores]

    def contains(self, lang):
        return lang in self.lang_countries

    def get(self, lang):
        return self.lang_countries[lang]


class PagelangsFeature:
    def __init__(self, page_provider=None, country_provider=None):
        if not page_provider: page_provider = PagelangProvider()
        if not country_provider: country_provider = CountrylangProvider()

        self.page_provider = page_provider
        self.country_provider = country_provider

        self.name = 'pagelang'

    def infer(self, url):
        if not self.page_provider.contains(url):
            return (0, {})
        lang = self.page_provider.get(url)
        if not self.country_provider.contains(lang):
            return (0, {})

        candidates = dict(self.country_provider.get(lang))

        return (0.70, candidates)


def test_pagelang_provider():
    provider = PagelangProvider('goldfeatures/pagelangs.tsv')
    assert(not provider.contains('foo'))
    assert(provider.contains('http://www.bfs.admin.ch/bfs/portal/de/index/themen/16/02/02/data.html'))
    assert(provider.get('http://www.bfs.admin.ch/bfs/portal/de/index/themen/16/02/02/data.html') == 'de')


def test_country_provider():

    provider = CountrylangProvider()
    assert(not provider.contains('foo'))
    assert(provider.contains('en'))
    en = provider.get('en')
    assert(en[0][0] == 'us')
    assert(abs(en[0][1] - 0.6664) < 0.001)
    assert(en[1][0] == 'gb')
    assert(abs(en[1][1] - 0.2469) < 0.001)
    assert(en[2][0] == 'ca')
    assert(abs(en[2][1] - 0.0353) < 0.001)
    assert(en[3][0] == 'in')
    assert(abs(en[3][1] - 0.0280) < 0.001)
    es = provider.get('es')
    assert(es[0][0] == 'us')
    assert(es[1][0] == 'es')
    assert(es[2][0] == 'mx')
    assert(es[3][0] == 'ar')

    de = provider.get('de')
    assert(de[0][0] == 'de')
    assert(de[1][0] == 'ch')
    assert(de[2][0] == 'at')
    assert(de[3][0] == 'it')


def test_feature():
    page_provider = PagelangProvider('goldfeatures/pagelangs.tsv')
    country_provider = CountrylangProvider()
    feature = PagelangsFeature(page_provider, country_provider)
    assert(feature.infer('foo') == (0, {}))
    dist = feature.infer('http://www.bfs.admin.ch/bfs/portal/de/index/themen/16/02/02/data.html')
    assert(dist[0] == 0.70)
    assert(dist[1] == dict(country_provider.get('de')))
