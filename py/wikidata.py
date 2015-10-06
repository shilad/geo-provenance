"""
Attempts to look up the locations associated with URLs using information from Wikidata.

Uses a precomputed mapping from domain to coordinate extracted from the Wikidata project.
This mapping is stored in data/wikidata.json and can be rebuilt by running this Python module.

Author: Shilad Sen

"""
import json

import os
import traceback

from gputils import *

class WikidataProvider:
    """
    Resolves a URL to a country using information from the Wikidata project.
    Uses a precomputed mapping from domain to lat/long coordinate stored in data/wikidata.json.
    These coordinates are geocoded to country on the fly using OpenStreetMap's nominatom API.
    Results are cached so that domains are only geocoded once.
    """
    def __init__(self, cache_path=None):
        if not cache_path: cache_path = get_feature_data_path('wikidata')
        if not os.path.isfile(cache_path):
            raise GPException('wikidata results not available...')
        self.cache_path = cache_path

        warn('reading wikidata results...')
        n = 0
        self.domains = {}
        for line in gp_open(self.cache_path):
            tokens = line.split('\t')
            if len(tokens) == 2:
                domain = tokens[0].strip()
                iso = tokens[1].strip()
                if not iso: iso = None
                self.domains[domain] = iso
                n += 1
            else:
                warn('invalid wikidata line: %s' % `line`)
        warn('finished reading %d wikidata entries' % n)

        f = open(get_data_path('wikidata.json'))
        self.domain_coords = json.load(f)
        f.close()

    def get(self, url):
        domain = url2registereddomain(url)
        if not domain:
            return None
        r = self.domains.get(domain)
        if r:
            return r
        elif domain in self.domain_coords:
            coords = self.domain_coords[domain]
            cc = coord_to_country(coords)
            self.domains[domain] = cc
            self.add_cache_line(domain + u'\t' + (cc if cc else ''))
            return cc
        else:
            return None

    def add_cache_line(self, line):
        f = gp_open(self.cache_path, 'a')
        f.write(line + u'\n')
        f.close()

class WikidataFeature:
    def __init__(self, provider=None):
        if not provider: provider = WikidataProvider()
        self.provider = provider
        self.name = 'wikidata'

    def infer(self, url):
        r = self.provider.get(url)
        if r:
            return (0.99, { r : 1.0 })
        else:
            return (0, {})

def test_wikidata():
    provider = WikidataProvider()
    assert(not provider.get('foo'))
    assert(provider.get('http://www.ac.gov.br') == 'br')
    assert(provider.get('https://www.ac.gov.br') == 'br')
    assert(provider.get('https://www.ibm.com/foo/bar') == 'us')


def test_coord_to_country():
    assert(coord_to_country("25.269722|55.309444|0.000000|0") == 'ae')


def coord_to_country(wikidata_coord):
    parts = wikidata_coord.split('|')
    lat = float(parts[0])
    lng = float(parts[1])

    url = 'http://nominatim.openstreetmap.org/reverse?format=json&lat=%.4f&lon=%.4f' % (lat, lng)
    f = urllib2.urlopen(url)
    js = json.load(f)
    if js and js['address'] and js['address']['country_code']:
        return js['address']['country_code']
    else:
        return None

def rebuild():
    all_urls = 'http://wdq.wmflabs.org/api?props=856,159,625&q=CLAIM[856]%20AND%20(CLAIM[159]%20OR%20CLAIM[625])'

    all_data = json.load(urllib2.urlopen(all_urls))

    item_urls = {}
    for (item, type, url) in all_data['props']['856']:
        item_urls[item] = url

    domain_coords = {}
    for (item, type, coord) in all_data['props']['625']:
        url = item_urls[item]
        domain = url2registereddomain(url)
        domain_coords[domain] = coord

    for (i, (item, type, placeId)) in enumerate(all_data['props']['159']):
        if i % 10 == 0:
            warn('doing %d' % i)
        domain = url2registereddomain(item_urls[item])
        if domain in domain_coords: continue
        place_url = 'http://wdq.wmflabs.org/api?props=625&q=items[%s]' % placeId
        try:
            place_result = json.load(urllib2.urlopen(place_url))
            if 'props' in place_result and place_result['props'].get('625'):
                coord = place_result['props']['625'][0][2]
                domain_coords[domain] = coord
        except:
            warn('resolving %s failed:' % domain)
            traceback.print_exc()

    f = lambda u: u.encode('ascii', 'ignore')
    result = dict((f(k), f(v)) for (k, v) in domain_coords.items())
    f = open(DATA_DIR + '/wikidata.json', 'w')
    json.dump(result, f)
    f.close()

if __name__ == '__main__':
    rebuild()
