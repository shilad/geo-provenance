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
    import pprint; pprint.pprint(result)
    contact_countries = {}
    for (contact_type, contact_info) in result.get('contacts', {}).items():
        if not contact_info or not contact_info.get('country'): continue
        country_code = normalize_country(contact_info['country'], aliases)
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
            cc = normalize_country(tokens[-1].strip(), aliases)
            if cc: return cc
    for l in  [l for l in lines if ('admin country' in l)]:
        tokens = l.split(':')
        if len(tokens) > 1:
            cc = normalize_country(tokens[-1].strip(), aliases)
            if cc: return cc

    return None # Failure!

def extract_freetext_whois_country(records, regexes):
    joined = '\n'.join(records).lower()
    dist = {}
    for (tld, tld_rx) in regexes.items():
        n = len(re.findall(tld_rx, joined))
        if n > 0: dist[tld] = n
    return dist

def normalize_country(raw, aliases):
    raw = raw.strip().lower()
    if raw in aliases:
        return raw  # it's a literal TLD
    for tld in aliases:
        if raw in aliases[tld]:
            return tld
    return None

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


def test_parsed():
    aliases = read_aliases()
    records = [
        """
Whois Server Version 2.0

Domain names in the .com and .net domains can now be registered
with many different competing registrars. Go to http://www.internic.net
for detailed information.

   Domain Name: HARAREMUSIC.COM
   Registrar: WEBFUSION LTD.
   Sponsoring Registrar IANA ID: 1515
   Whois Server: whois.123-reg.co.uk
   Referral URL: http://www.123-reg.co.uk
   Name Server: NS.123-REG.CO.UK
   Name Server: NS2.123-REG.CO.UK
   Status: ok http://www.icann.org/epp#OK
   Updated Date: 23-oct-2014
   Creation Date: 16-nov-2006
   Expiration Date: 16-nov-2015

>>> Last update of whois database: Mon, 30 Mar 2015 16:51:09 GMT <<<

NOTICE: The expiration date displayed in this record is the date the
registrar's sponsorship of the domain name registration in the registry is
currently set to expire. This date does not necessarily reflect the expiration
date of the domain name registrant's agreement with the sponsoring
registrar.  Users may consult the sponsoring registrar's Whois database to
view the registrar's reported date of expiration for this registration.

TERMS OF USE: You are not authorized to access or query our Whois
database through the use of electronic processes that are high-volume and
automated except as reasonably necessary to register domain names or
modify existing registrations; the Data in VeriSign Global Registry
Services' ("VeriSign") Whois database is provided by VeriSign for
information purposes only, and to assist persons in obtaining information
about or related to a domain name registration record. VeriSign does not
guarantee its accuracy. By submitting a Whois query, you agree to abide
by the following terms of use: You agree that you may use this Data only
for lawful purposes and that under no circumstances will you use this Data
to: (1) allow, enable, or otherwise support the transmission of mass
unsolicited, commercial advertising or solicitations via e-mail, telephone,
or facsimile; or (2) enable high volume, automated, electronic processes
that apply to VeriSign (or its computer systems). The compilation,
repackaging, dissemination or other use of this Data is expressly
prohibited without the prior written consent of VeriSign. You agree not to
use electronic processes that are automated and high-volume to access or
query the Whois database except as reasonably necessary to register
domain names or modify existing registrations. VeriSign reserves the right
to restrict your access to the Whois database in its sole discretion to ensure
operational stability.  VeriSign may restrict or terminate your access to the
Whois database for failure to abide by these terms of use. VeriSign
reserves the right to modify these terms at any time.

The Registry database contains ONLY .COM, .NET, .EDU domains and
Registrars.

For more information on Whois status codes, please visit
https://www.icann.org/resources/pages/epp-status-codes-2014-06-16-en.
Domain Name: HARAREMUSIC.COM
Registry Domain ID: 673232892_DOMAIN_COM-VRSN
Registrar WHOIS Server: whois.meshdigital.com
Registrar URL: http://www.domainbox.com
Updated Date: 2014-10-23T00:00:00Z
Creation Date: 2006-11-16T00:00:00Z
Registrar Registration Expiration Date: 2015-11-16T00:00:00Z
Registrar: WEBFUSION LIMITED
Registrar IANA ID: 1515
Registrar Abuse Contact Email: support@domainbox.com
Registrar Abuse Contact Phone: +1.8779770099
Reseller: 123Reg/Webfusion
Domain Status: ok
Registry Registrant ID:
Registrant Name: Kudaushe Matimba
Registrant Organization:
Registrant Street: 76 Purbrook Estate, Tower Bridge Road
Registrant City: London
Registrant State/Province: England
Registrant Postal Code: SE1 3DA
Registrant Country: GB
Registrant Phone: +44.7939415405
Registrant Phone Ext:
Registrant Fax Ext:
Registrant Email: kudaushe@gmail.com
Registry Admin ID:
Admin Name: Kudaushe Matimba
Admin Organization:
Admin Street: 76 Purbrook Estate, Tower Bridge Road
Admin City: London
Admin State/Province: England
Admin Postal Code: SE1 3DA
Admin Country: GB
Admin Phone: +44.7939415405
Admin Phone Ext:
Admin Fax Ext:
Admin Email: kudaushe@gmail.com
Registry Tech ID:
Tech Name: Webfusion Ltd.
Tech Organization:
Tech Street: 5 Roundwood Avenue
Tech City: Stockley Park
Tech State/Province: Uxbridge
Tech Postal Code: UB11 1FF
Tech Country: GB
Tech Phone: +44.8454502310
Tech Phone Ext:
Tech Fax Ext:
Tech Email: yoursupportrequest@123-reg.co.uk
Name Server: ns.123-reg.co.uk
Name Server: ns2.123-reg.co.uk
DNSSEC: unsigned
URL of the ICANN WHOIS Data Problem Reporting System: http://wdprs.internic.net/
>>> Last update of WHOIS database: 2015-03-30T17:51:27Z <<<

The Data in this WHOIS database is provided
for information purposes only, and is designed to assist persons in
obtaining information related to domain name registration records.
It's accuracy is not guaranteed. By submitting a
WHOIS query, you agree that you will use this Data only for lawful
purposes and that, under no circumstances will you use this Data to:
(1) allow, enable, or otherwise support the transmission of mass
unsolicited, commercial advertising or solicitations via e-mail(spam);
 or (2) enable high volume, automated, electronic processes that
apply to this WHOIS or any of its related systems. The provider of
this WHOIS reserves the right to modify these terms at any time.
By submitting this query, you agree to abide by this policy.

LACK OF A DOMAIN RECORD IN THE WHOIS DATABASE DOES
NOT INDICATE DOMAIN AVAILABILITY.
        """
        ]
    freetext = extract_parsed_whois_country(records, read_countries(), aliases)
    assert(freetext == 'gb')