"""
Attempts to look up the locations associated with URLs using information from Wikidata.

TODO: Incorporate udpated information from the following API query:

http://wdq.wmflabs.org/api?q=CLAIM[856]%20AND%20CLAIM[625]&props=856,625

"""
import json

import os
import traceback

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


def test_rebuild():
    rebuild()

def test_coord_to_country():
    assert(coord_to_country("25.269722|55.309444|0.000000|0") == 'ae')


NOMINATIM = None

def coord_to_country(wikidata_coord):
    global NOMINATIM

    if not NOMINATIM:
        from geopy.geocoders import Nominatim
        NOMINATIM = Nominatim()

    parts = wikidata_coord.split('|')
    lat = float(parts[0])
    lng = float(parts[1])

    location = NOMINATIM.reverse(str(lat) + "," + str(lng))
    if location and location.raw and 'address' in location.raw:
        return location.raw['address'].get('country_code')
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
