import os

from gputils import *

class BatchWikidataProvider:
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
        return self.domains[url2registereddomain(url)]

    def contains(self, url):
        return url2registereddomain(url) in self.domains

class WikidataFeature:
    def __init__(self, provider=None):
        if not provider: provider = BatchWikidataProvider()
        self.provider = provider
        self.name = 'wikidata'

    def infer(self, url):
        if self.provider.contains(url):
            return (0.99, { self.provider.get(url) : 1.0 })
        else:
            return (0, {})

def test_wikidata():
    provider = BatchWikidataProvider()
    assert(not provider.contains('foo'))
    assert(provider.contains('http://www.ac.gov.br'))
    assert(provider.get('http://www.ac.gov.br') == 'br')
    assert(provider.get('https://www.ac.gov.br') == 'br')
