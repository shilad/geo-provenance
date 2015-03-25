import os

from gputils import *

class BatchWhoisProvider:
    def __init__(self, path=None):
        if not path: path = get_feature_data_path('whois')
        if not os.path.isfile(path):
            raise GPException('whois results not available.')

        warn('reading whois results...')
        nlines = 0
        self.parsed = {}
        self.freetext = {}
        for line in gp_open(path):
            tokens = line.strip().split('\t')
            if len(tokens) == 2:
                domain = tokens[0]
                whois = tokens[1]
                if whois.endswith('|p'):
                    country = whois[:-2]
                    if country != '??': self.parsed[domain] = country
                else:
                    dist = {}
                    for pair in whois.split(','):
                        (country, n) = pair.split('|')
                        dist[country] = int(n)
                    total = 1.0 * sum(dist.values())
                    if sum > 0:
                        for c in dist: dist[c] /= total
                        self.freetext[domain] = dist
                nlines += 1
            else:
                warn('invalid whois line: %s' % `line`)
        warn('finished reading %d whois entries' % nlines)

    def getParsed(self, url):
        return self.parsed[url2registereddomain(url)]

    def containsParsed(self, url):
        return url2registereddomain(url) in self.parsed

    def getFreetext(self, url):
        return self.freetext[url2registereddomain(url)]

    def containsFreetext(self, url):
        return url2registereddomain(url) in self.freetext

class ParsedWhoisFeature:
    def __init__(self, provider=None):
        if not provider: provider = BatchWhoisProvider()
        self.provider = provider
        self.name = 'parsed_whois'

    def infer(self, url):
        if self.provider.containsParsed(url):
            return (0.99, { self.provider.getParsed(url) : 1.0 })
        else:
            return (0, {})


class FreetextWhoisFeature:
    def __init__(self, provider=None):
        if not provider: provider = BatchWhoisProvider()
        self.provider = provider
        self.name = 'freetext_whois'

    def infer(self, url):
        if self.provider.containsFreetext(url):
            return (0.60, self.provider.getFreetext(url))
        else:
            return (0, {})

def test_parsed_whois():
    provider = BatchWhoisProvider('goldfeatures/whois.tsv')
    assert(not provider.containsParsed('foo'))
    assert(provider.containsParsed('http://www.unesco.org/foo/bar'))
    assert(provider.getParsed('http://www.unesco.org/foo/bar') == 'fr')
    assert(provider.containsParsed('http://budapestbylocals.com/foo/bar'))
    assert(provider.getParsed('http://budapestbylocals.com/foo/bar') == 'hu')


def test_freetext_whois():
    provider = BatchWhoisProvider('goldfeatures/whois.tsv')
    assert(provider.containsFreetext('http://foo.google.ca/foo/bar'))
    assert(provider.getFreetext('http://foo.google.ca/foo/bar'), {'us' : 0.5, 'ca' : 0.5})
