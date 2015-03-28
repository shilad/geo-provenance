"""

A module that extracts countries from whois records.
Adapted by Shilad Sen from ruby code developed by Dave Musicant.

There are two strategies used to extract whois records:

1. Parsed extractions, where the structure of a whois record is
analyzed and the administrative country is extracted from the
appropriate field.

2. Freetext extractions, where a whois record is scanned for known
aliases to countries.

The parsed strategy is always favored, and the freetext strategy is
only used as a last resort.

"""

import collections
import os
import re

import pythonwhois

from gputils import *

from country import read_countries

class WhoisProvider:
    """
        A provided that resolves countries associated with a whois record.
        A cache is kept so that whois records are only queried once.
    """
    def __init__(self, cache_path=None):
        self.cache_path = cache_path
        if not self.cache_path:
            self.cache_path = get_feature_data_path('whois')
        if not os.path.isfile(self.cache_path):
            raise GPException('whois cache %s does not exist.' % self.cache_path)

        warn('reading whois results...')
        nlines = 0
        self.cache = {}
        f = gp_open(self.cache_path)
        for line in f:
            tokens = line.split('\t')
            if len(tokens) == 2:
                domain = tokens[0].strip()
                whois = tokens[1].strip()
                if not whois:
                    self.cache[domain] = {}
                elif whois.endswith('|p'):
                    country = whois[:-2]
                    if country != '??': self.cache[domain] = country
                else:
                    dist = {}
                    for pair in whois.split(','):
                        (country, n) = pair.split('|')
                        dist[country] = int(n)
                    total = 1.0 * sum(dist.values())
                    if sum > 0:
                        for c in dist: dist[c] /= total
                    self.cache[domain] = dist
                nlines += 1
            else:
                warn('invalid whois line: %s' % `line`)
        warn('finished reading %d whois entries' % nlines)
        f.close()

        self.countries = read_countries()
        self.aliases = read_aliases()
        self.regexes = build_regexes(self.aliases)

    def getParsed(self, url):
        """
        Retrieves the country code associated with a URL using the structured
        strategy, or returns None if it does not succeed.
        """
        d = url2registereddomain(url)
        if not d:
            return None
        if d not in self.cache:
            self.add_to_cache(d)
        if d not in self.cache or type(self.cache[d]) not in (type(''), type(u'')):
            return None
        return self.cache[d]

    def getFreetext(self, url):
        """
        Calculates a dicitionary mapping country codes to the number of
        mentions of them in the whois record. Returns None on failure, and an
        empty dictionary if no entities are found.
        """
        d = url2registereddomain(url)
        if not d:
            return None
        if d not in self.cache:
            self.add_to_cache(d)
        if d not in self.cache or type(self.cache[d]) != type({}):
            return None
        return self.cache[d]

    def add_to_cache(self, domain):
        raw = None
        try:
            raw = retrieve_whois_record(domain)
        except:
            warn('whois lookup for %s failed: %s' % (domain, sys.exc_info()[1]))
            self.cache[domain] = {}
            self.add_cache_line(domain + u'\t')
            return

        try:
            parsed = extract_parsed_whois_country(raw, self.countries, self.aliases)
            if parsed:
                self.cache[domain] = parsed
                self.add_cache_line(domain + u'\t' + parsed + '|p')
                return
        except:
            warn('parsing of whois record for %s failed: %s. Resorting to freetext method.'
                 % (domain, sys.exc_info()[1]))

        freetext = extract_freetext_whois_country(raw, self.regexes)
        if freetext:
            self.cache[domain] = freetext
            pairs = [u'%s|%s' % (cc, n) for (cc, n) in freetext.items()]
            self.add_cache_line(domain + u'\t' + u','.join(pairs))

    def add_cache_line(self, line):
        f = gp_open(self.cache_path, 'a')
        f.write(line + u'\n')
        f.close()

PROVIDER_INST = None

class ParsedWhoisFeature:
    def __init__(self, provider=None):
        global PROVIDER_INST
        if not provider:
            if not PROVIDER_INST: PROVIDER_INST = WhoisProvider()
            provider = PROVIDER_INST
        self.provider = provider
        self.name = 'parsed_whois'

    def infer(self, url):
        r = self.provider.getParsed(url)
        if r:
            return (0.60, { r : 1.0 })
        else:
            return (0, {})

class FreetextWhoisFeature:
    def __init__(self, provider=None):
        global PROVIDER_INST
        if not provider:
            if not PROVIDER_INST: PROVIDER_INST = WhoisProvider()
            provider = PROVIDER_INST
        self.provider = provider
        self.name = 'freetext_whois'

    def infer(self, url):
        r = self.provider.getFreetext(url)
        if r:
            t = 1.0 * sum(r.values())
            return 0.6, dict((c, n / t) for c, n in r.items())
        else:
            return (0, {})


def retrieve_whois_record(domain):
    """
    Retrieves a list of WhoIs records, each of which is a string. Most domains
    will only have one record, but some may require recursive lookups.
    """
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
    warn('building country alias regexes')
    n = 0
    regexes = {}
    for (cc, aliases) in aliases.items():
        if cc == 'atrysh': print aliases
        orred = '|'.join(re.escape(a) for a in aliases)
        pattern = "(^|\\b)(" + orred + ')($|\\b)'
        regexes[cc] = re.compile(pattern)
        n += len(aliases)
    warn('finished building %d country alias regexes' % n)
    return regexes


def read_aliases(dir=DATA_DIR):
    ambiguous = {}
    for line in gp_open(dir + '/manual_aliases.tsv'):
        tokens = line.split('\t')
        alias = tokens[0].strip().lower()
        code = tokens[1].strip().lower()
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

def test_parsed_provider():
    provider = WhoisProvider()
    assert(not provider.getParsed('foo'))
    assert(provider.getParsed('http://www.unesco.org/foo/bar') == 'fr')
    assert(provider.getParsed('http://budapestbylocals.com/foo/bar') == 'hu')

def test_freetext_provider():
    provider = WhoisProvider()
    assert(provider.getFreetext('http://foo.google.ca/foo/bar') == {'us' : 0.5, 'ca' : 0.5})

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
    assert(freetext == {'us' : 3})


def test_regex():
    aliases = read_aliases()
    regexes = build_regexes(aliases)
    records = [
        """
%
%AM TLD whois server #2
%

   Domain name: tert.am
   Registar:    abcdomain (ABCDomain LLC)
   Status:      active

   Registrant:
      TERT AM LLC
      Krivoy alley, home 22
      Yerevan,  0015
      AM

   Administrative contact:
      TERT AM LLC
      Krivoy alley, home 22
      Yerevan, 0015
      AM
      editor@tert.am
      060528528, 096837826

   Technical contact:
      TERT AM LLC
      Krivoy alley, home 22
      Yerevan, 0015
      AM
      sardaryan.h@gmail.com
      060528528, 096837826

   DNS servers:
      ivy.ns.cloudflare.com
      nick.ns.cloudflare.com

   Registered:    2013-07-01
   Last modified: 2015-01-28
   Expires:       2016-07-01
        """
        ]
    freetext = extract_freetext_whois_country(records, regexes)
    assert(freetext == None)