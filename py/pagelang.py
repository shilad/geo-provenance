"""
A module to infer the country of a webpage by detecting its language and then
 identifying the most likely countries to write in that language.

 Code for scraping webpages can be found in the "downloader" module.
 The language of a webpage is inferred using Python's langid module.
 The mapping from language to most likely countries is calculated by
 combining prior probabilities for a country generating any web
 resource with the ranking of a language's prominence for a country as
 specified in geonames.

 Author: Shilad Sen
"""


import collections
import os
import langid
import sys

from gputils import *

from downloader import url_to_text

import country


class PagelangProvider:
    """
    Determines the language associated with a URL.
    Caches results so that each page is crawled just once.
    """
    def __init__(self, cache_path=None):
        if not cache_path: cache_path = get_feature_data_path('pagelangs')
        if not os.path.isfile(cache_path):
            raise GPException('page language results not available...')
        self.cache_path = cache_path

        warn('reading pagelang results...')
        nlines = 0
        self.pagelangs = {}
        for line in gp_open(self.cache_path):
            tokens = line.strip().split('\t')
            if len(tokens) == 2:
                url = tokens[0]
                cc = tokens[1]
                if cc == 'unknown':
                    cc = None
                self.pagelangs[url] = cc
                nlines += 1
            else:
                warn('invalid pagelang line: %s' % `line`)
        warn('finished reading %d pagelang entries' % nlines)

    def get(self, url):
        if url not in self.pagelangs:
            lang = None
            try:
                text = url_to_text(url)
                if text:
                    (l, confidence) = langid.classify(text)
                    if confidence >= 0.9:
                        lang = l
            except:
                warn('language detection scraping for %s failed: %s' % (url, sys.exc_info()[1]))
            self.pagelangs[url] = lang
            self.add_cache_line(url + u'\t' + (lang if lang else 'unknown'))
        return self.pagelangs[url]

    def add_cache_line(self, line):
        f = gp_open(self.cache_path, 'a')
        f.write(line + u'\n')
        f.close()


class CountrylangProvider:
    """
    Determines the mapping between languages and most likely countries.
    """
    def __init__(self, countries=None):
        if not countries:
            countries = country.read_countries()
        iso_countries = dict([(c.iso, c) for c in countries])

        # calculate language to country mapping
        # Number of second-language speakers (or higher) for a country c
        # and language l is a function of l's rank popularity for c.
        # The function is exponentially decreasing.
        lang2countries = collections.defaultdict(list)
        for c in iso_countries.values():
            for (i, l) in enumerate(c.cleaned_langs):
                s = c.prior * 1.0 / ((i+1) ** 2.5)
                lang2countries[l].append((s, c.iso))

        self.lang_countries = {}
        for lang, country_scores in lang2countries.items():
            country_scores.sort()
            country_scores.reverse()
            sum_scores = 1.0 * sum([s for (s, c) in country_scores]) + 0.000001
            self.lang_countries[lang] = [(c, score/sum_scores) for (score, c) in country_scores]

    def get(self, lang):
        return self.lang_countries.get(lang)


class PagelangsFeature:
    def __init__(self, page_provider=None, country_provider=None):
        if not page_provider: page_provider = PagelangProvider()
        if not country_provider: country_provider = CountrylangProvider()

        self.page_provider = page_provider
        self.country_provider = country_provider

        self.name = 'pagelang'

    def infer(self, url):
        lang = self.page_provider.get(url)
        if not lang:
            return (0, {})

        candidates = dict(self.country_provider.get(lang))
        if not candidates:
            return (0, {})

        return (0.70, candidates)


def test_offline_pagelang_provider():
    provider = PagelangProvider()
    assert(not provider.get('foo'))
    assert(provider.get('http://www.bfs.admin.ch/bfs/portal/de/index/themen/16/02/02/data.html') == 'de')


def test_online_pagelang_provider():
    provider = PagelangProvider()
    assert(provider.get('http://www.shilad.com') == 'en')


def test_country_provider():

    provider = CountrylangProvider()
    assert(not provider.get('foo'))
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
    page_provider = PagelangProvider()
    country_provider = CountrylangProvider()
    feature = PagelangsFeature(page_provider, country_provider)
    assert(feature.infer('foo') == (0, {}))
    dist = feature.infer('http://www.bfs.admin.ch/bfs/portal/de/index/themen/16/02/02/data.html')
    assert(dist[0] == 0.70)
    assert(dist[1] == dict(country_provider.get('de')))
