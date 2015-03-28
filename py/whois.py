import collections
import os
import re

import pythonwhois

from gputils import *

from country import read_countries

class OfflineWhoisProvider:
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
        return self.parsed.get(url2registereddomain(url))

    def getFreetext(self, url):
        return self.freetext.get(url2registereddomain(url))

class ParsedWhoisFeature:
    def __init__(self, provider=None):
        if not provider: provider = OfflineWhoisProvider()
        self.provider = provider
        self.name = 'parsed_whois'

    def infer(self, url):
        r = self.provider.getParsed(url)
        if r:
            return (0.60, r)
        else:
            return (0, {})


class OnlineWhoisProvider:
    def __init__(self, delegate=None):
        self.delegate = delegate
        self.aliases = {}
        self.tld_to_countries = {}

        # for c in read_countries():
        #     if c.tld in self.tld_to_countries:
        #         warn('tld %s shared betweee %s and %s' % (c.tld, c.name, self.tld_to_countries[c.tld].name))
        #     self.tld_to_countries[c.tld] = c

    def getParsed(self, url):
        d = url2registereddomain(url)
        if self.delegate:
            r = self.delegate.getParsed(d)
            if r: return r

    def getFreetext(self, url):
        d = url2registereddomain(url)
        if self.delegate:
            r = self.delegate.getFreetext(d)
            if r: return r

def retrieve_whois_record(domain):
    return pythonwhois.net.get_whois_raw(domain)


def extract_parsed_whois_country(records, countries, aliases):

    # First try to extract a parsed record
    result = pythonwhois.parse.parse_raw_whois(records)
    contact_countries = {}
    for (contact_type, contact_info) in result.get('contacts', {}).items():
        if not contact_info or not contact_info.get('country'): continue
        country_code = normalize_country(contact_info['country'], countries, aliases)
        if country_code: contact_countries[contact_type] = country_code
    if contact_countries:
        for type in ('admin', 'tech', 'registrant'):
            if type in contact_countries:
                print 'returning', type
                return contact_countries[type]
        return list(contact_countries.values())[0]

    # Try Dave's heuristics
    lines = [l.lower() for l in '\n'.join(records).split('\n')]
    for l in  [l for l in lines if ('admin' in l and 'country code' in l)]:
        tokens = l.split(':')
        if len(tokens) > 1:
            cc = normalize_country(tokens[-1].strip(), countries, aliases)
            if cc: return cc
    for l in  [l for l in lines if ('admin country' in l)]:
        tokens = l.split(':')
        if len(tokens) > 1:
            cc = normalize_country(tokens[-1].strip(), countries, aliases)
            if cc: return cc

    return None # Failure!

def extract_freetext_whois_country(records, regexes):
    joined = '\n'.join(records).lower()
    dist = {}
    for (tld, tld_rx) in regexes.items():
        n = len(re.findall(tld_rx, joined))
        if n > 0: dist[tld] = n
    return dist

def normalize_country(raw, countries, aliases):
    raw = raw.strip().lower()
    if len(raw) < 2: return None
    if len(raw) == 2:
        for c in countries:
            if c.tld == raw:
                return raw
            elif c.name.lower() == raw:
                return c.tld
    return aliases.get(raw) # may be none

def build_regexes(aliases):
    regexes = {}
    for (cc, aliases) in aliases.items():
        if cc != 'us': continue
        pattern = "(^|\\b)(" + '|'.join(aliases) + ')($|\\b)'
        regexes[cc] = re.compile(pattern)
    return regexes


def read_aliases(dir=DATA_DIR):
    ambiguous = {}
    for line in gp_open(dir + '/manual_aliases.tsv'):
        tokens = line.split('\t')
        code = tokens[0].strip().lower()
        alias = tokens[1].strip().lower()
        ambiguous[alias] = code

    mapping = dict(ambiguous)
    for line in gp_open(dir + '/geonames_aliases.tsv'):
        tokens = line.split('\t')

        code = tokens[8].strip().lower()
        for alias in tokens[3].strip().lower().split(","):
            if len(alias) <= 3:
                pass
            elif alias in ambiguous:
                pass    # already handled
            elif alias in mapping and mapping[alias] != code:
                warn('duplicate alias %s between %s and %s' % (alias, code, mapping[alias]))
            else:
                mapping[alias] = code

    aliases = collections.defaultdict(list)
    for (alias, cc) in mapping.items():
        aliases[cc].append(alias)

    return dict(aliases)


class FreetextWhoisFeature:
    def __init__(self, provider=None):
        if not provider: provider = OfflineWhoisProvider()
        self.provider = provider
        self.name = 'freetext_whois'

    def infer(self, url):
        r = self.provider.getFreetext(url)
        if r:
            return (0.60, r)
        else:
            return (0, {})

def test_parsed_offline_whois():
    provider = OfflineWhoisProvider()
    assert(not provider.getParsed('foo'))
    assert(provider.getParsed('http://www.unesco.org/foo/bar') == 'fr')
    assert(provider.getParsed('http://budapestbylocals.com/foo/bar') == 'hu')

def test_freetext_offline_whois():
    provider = OfflineWhoisProvider()
    assert(provider.getFreetext('http://foo.google.ca/foo/bar'), {'us' : 0.5, 'ca' : 0.5})

def test_online_whois():
    countries = read_countries()
    aliases = read_aliases()
    records = retrieve_whois_record('shilad.com')
    assert('Shilad Sen' in records[0])
    assert(extract_parsed_whois_country(records, countries, aliases) == 'us')
    records = retrieve_whois_record('porsche.com')
    assert(extract_parsed_whois_country(records, countries, aliases) == 'de')

def test_freetext_whois():
    aliases = read_aliases()
    records = retrieve_whois_record('macalester.edu')
    # print '\n'.join(records)
    regexes = build_regexes(aliases)
    freetext = extract_freetext_whois_country(records, regexes)
    assert(freetext == None)

