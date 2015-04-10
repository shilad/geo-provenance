import json

from gputils import *
from whois import read_aliases
from country import read_countries
from pagelang import CountrylangProvider

domain_coords = json.load(open(get_data_path('wikidata.json')))
aliases = read_aliases()
countries = read_countries()

def write_json(var_name, data, path):
    f = gp_open(path, 'w')
    s = json.dumps(data)
    f.write(u'var %s = %s;\n' % (var_name, s))
    f.close()

country_json = []
for c in countries:
    country_json.append({
        'iso' : c.iso,
        'name' : c.name,
        'tld' : c.tld,
        'langs' : c.cleaned_langs,
        'prior' : c.prior,
    })
write_json('GP_COUNTRIES', country_json, '../js/country_data.js')

alias_json = {}
for iso in aliases:
    for a in aliases[iso]:
        alias_json[a] = iso
write_json('GP_ALIASES', alias_json, '../js/alias_data.js')

coord_json = {}
for (host, coords) in domain_coords.items():
    coord_json[host] = ','.join(coords.split('|')[:2])
write_json('GP_WIKIDATA_COORDS', coord_json, '../js/wikidata_data.js')



lang_prov = CountrylangProvider()
langs = set(sum([c.cleaned_langs for c in countries], []))
lang_json = {}
for l in langs:
    results = lang_prov.get(l)
    if results:
        lang_json[l] = results
write_json('GP_LANG_TO_COUNTRY', lang_json, '../js/lang_data.js')
