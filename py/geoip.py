import traceback
import urllib
import os

from gputils import *

class BatchGeoIpProvider:
    def __init__(self, path=None):
        if not path: path = get_feature_data_path('geoip')
        if not os.path.isfile(path):
            raise GPException('geoip results not available...')

        warn('reading geoip results...')
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
                warn('invalid geoip line: %s' % `line`)
        warn('finished reading %d geoip entries' % n)

    def get(self, url):
        return self.domains[url2registereddomain(url)]

    def contains(self, url):
        return url2registereddomain(url) in self.domains

def geocode_url(url):
    h = url2host(url)
    try:
        s = urllib.urlopen('http://freegeoip.net/csv/' + h).read()
        tokens = s.split(',')
        if len(tokens) > 2 and len(tokens[1]) == 2:
            cc = tokens[1].lower()
            if cc == 'uk': cc = 'gb'
            return cc
        else:
            warn("invalid response for host %s: %s" % (h, tokens))
            return None
    except:
        warn('geocoding ip failed for: %s' % h)
        traceback.print_exc()
        return None


class GeoIPFeature:
    def __init__(self, provider=None):
        if not provider: provider = BatchGeoIpProvider()
        self.provider = provider
        self.name = 'geoip'

    def infer(self, url):
        if self.provider.contains(url):
            return (0.80, { self.provider.get(url) : 1.0 })
        else:
            return (0, {})



def test_geoip():
    provider = BatchGeoIpProvider()
    assert(not provider.contains('foo'))
    assert(provider.contains('http://www.ac.gov.br'))
    assert(provider.get('http://www.ac.gov.br') == 'br')
    assert(provider.get('https://www.ac.gov.br') == 'br')


# def test_milgov():
#     f = MilGovFeature()
#     assert(f.infer_dist('http://foo.bbc.com/bar') == (0, {}))
#     assert(f.infer_dist('https://whitehouse.gov/blah/de') == (1.0, { 'us' : 1.0}))

def test_url2country():
    assert(geocode_url('https://google.com/foo') == 'us')

def build():
    f = gp_open('../data/goldfeatures/geoip.tsv', 'w')
    domains = set()
    for (url, cc) in read_gold():
        d = url2registereddomain(url)
        if d not in domains:
            domains.add(d)
            c = geocode_url(url)
            if c:
                f.write(d + u'\t' + c + u'\n')
    f.close()

if __name__ == '__main__':
    build()