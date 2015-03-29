import codecs
import sys
import tldextract
import urllib2


DATA_DIR = '../data'
FEATURE_DIR = '../data/goldfeatures'

GENERIC_TLDS = set('ad,as,bz,cc,cd,co,dj,fm,io,la,me,ms,nu,sc,sr,su,tv,tk,ws,int'.split(','))

def get_feature_data_path(name):
    return FEATURE_DIR + '/' + name + '.tsv'

def get_data_path(filename):
    return DATA_DIR + '/' + filename

def set_data_dir(path):
    global DATA_DIR
    DATA_DIR = path

def set_feature_dir(path):
    global FEATURE_DIR
    FEATURE_DIR = path

def url2registereddomain(url):
    host = url2host(url)
    parts = tldextract.extract(host)
    return parts.registered_domain

def url2tld(url):
    host = url2host(url)
    return host.split('.')[-1]

def warn(message):
    sys.stderr.write(message + '\n')

def read_gold(path=None):
    if not path: path = get_data_path('geoprov198.tsv')
    f = gp_open(path)
    gold = [
        (l.split('\t')[0].strip(), l.split('\t')[1].strip())
        for l in f
    ]
    f.close()
    return list(gold)

# The encoded reader from io is faster but only available in Python >= 2.6
try:
    import io
    enc_open = io.open
except:
    enc_open = codecs.open


class GPException(Exception):
    pass

def gp_open(path, mode='r', encoding='utf-8'):
    return enc_open(path, mode, encoding=encoding)

def url2host(url):
    if not url.startswith('http:') and not url.startswith('https:'):
        url = 'http://' + url
    return urllib2.urlparse.urlparse(url).netloc


def test_url2host():
    assert(url2host('www.ibm.com/foo/bar') == 'www.ibm.com')
    assert(url2host('http://www.ibm.com/foo/bar') == 'www.ibm.com')
    assert(url2host('https://www.ibm.com/foo/bar') == 'www.ibm.com')

def test_url2tld():
    assert(url2tld('http://www.ibm.com/foo/bar') == 'com')

def test_url2registereddomain():
    assert(url2registereddomain('http://www.ibm.com/foo/bar') == 'ibm.com')
    assert(url2registereddomain('http://foo.bbc.co.uk/foo/bar') == 'bbc.co.uk')