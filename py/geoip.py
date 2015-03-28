"""
Geocodes the country of a website by geocoding the server's IP address.
This signal is very unreliable, but may be better than nothing.

 Authored by Shilad Sen.
"""


import traceback
import urllib
import os

from gputils import *

class GeoIpProvider:
    def __init__(self, path=None):
        self.cache_path = path
        if not self.cache_path: self.cache_path = get_feature_data_path('geoip')
        if not os.path.isfile(self.cache_path):
            raise GPException('geoip results not available...')

        warn('reading geoip results...')
        n = 0
        self.domains = {}
        for line in gp_open(self.cache_path):
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
        d = url2registereddomain(url)
        if d not in self.domains:
            c = geocode_url(url)
            if c:
                self.add_cache_line(d + u'\t' + c + u'\n')
            self.domains[d] = c
        return self.domains.get(d)

    def add_cache_line(self, line):
        f = gp_open(self.cache_path, 'a')
        f.write(line + u'\n')
        f.close()

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
        if not provider: provider = GeoIpProvider()
        self.provider = provider
        self.name = 'geoip'

    def infer(self, url):
        if self.provider.contains(url):
            return (0.80, { self.provider.get(url) : 1.0 })
        else:
            return (0, {})



def test_geoip():
    provider = GeoIpProvider()
    assert(not provider.get('foo'))
    assert(provider.get('http://www.ac.gov.br') == 'br')
    assert(provider.get('https://www.ac.gov.br') == 'br')


# def test_milgov():
#     f = MilGovFeature()
#     assert(f.infer_dist('http://foo.bbc.com/bar') == (0, {}))
#     assert(f.infer_dist('https://whitehouse.gov/blah/de') == (1.0, { 'us' : 1.0}))

def test_url2country():
    assert(geocode_url('https://google.com/foo') == 'us')