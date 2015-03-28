"""
Attempts to look up the locations associated with URLs using information from Wikidata.

TODO: Incorporate udpated information from the following API query:

http://wdq.wmflabs.org/api?q=CLAIM[856]%20AND%20CLAIM[625]&props=856,625

"""

import os

from gputils import *

class WikidataProvider:
    def __init__(self, path=None):
        if not path: path = get_feature_data_path('wikidata')
        if not os.path.isfile(path):
            raise GPException('wikidata results not available...')

        warn('reading wikidata results...')
        n = 0
        self.domains = {}
        for line in gp_open(path):
            tokens = line.strip().split('\t')
            if len(tokens) == 2:
                domain = tokens[0]
                iso = tokens[1]
                self.domains[domain] = iso
                n += 1
            else:
                warn('invalid wikidata line: %s' % `line`)
        warn('finished reading %d wikidata entries' % n)

    def get(self, url):
        return self.domains.get(url2registereddomain(url))

class WikidataFeature:
    def __init__(self, provider=None):
        if not provider: provider = WikidataProvider()
        self.provider = provider
        self.name = 'wikidata'

    def infer(self, url):
        if self.provider.contains(url):
            return (0.99, { self.provider.get(url) : 1.0 })
        else:
            return (0, {})

def test_wikidata():
    provider = WikidataProvider()
    assert(not provider.get('foo'))
    assert(provider.get('http://www.ac.gov.br') == 'br')
    assert(provider.get('https://www.ac.gov.br') == 'br')
