import chardet
import codecs
import os
import re
import shutil
import tempfile
import urlparse
import urllib2

from bs4 import BeautifulSoup

from gputils import *


BINARY_EXTS = set(['pdf', 'jpg', 'gif', 'xls', 'doc', 'png', 'zip', 'swf', 'tif', 'dot', 'jpeg', 'xlsx'])
BLOCKSIZE = 1048576 # or some other, desired size in bytes
ENCODING_DETECT_BYTES = 10*1024*1024   # 10 MBs


def encoding_works(path, encoding):
    f = None
    try:
        f = codecs.open(path, encoding=encoding)
        while f.read(BLOCKSIZE):
            pass
        return True
    except:
        return False
    finally:
        if f: f.close()


def guess_charset(response, download):
    ctype = response.headers.get('content-type', '').lower()
    if 'charset=' in ctype:
        charset = ctype.split('charset=')[-1]
        if encoding_works(download, charset):
            return charset

    s = codecs.open(download, encoding='ascii', errors='ignore').read(10000).lower()
    mat_meta = re.compile('<meta.*charset=(")?([a-z0-9_-]+)[^a-z0-9_-]').search
    m = mat_meta(s)
    if m:
        charset = m.group(2)
        if encoding_works(download, charset):
            return charset

    s = open(download, 'rb').read(ENCODING_DETECT_BYTES)
    d = chardet.detect(s)
    charset = d['encoding']
    if charset and encoding_works(download, charset):
        return charset

    return 'utf-8'


TMP_DIR = ".tmp"


def download_url(url):
    urlinfo = urlparse.urlparse(url)

    request = urllib2.Request(url)
    handler1 = urllib2.HTTPRedirectHandler()
    handler2 = urllib2.HTTPCookieProcessor()
    opener3 = urllib2.build_opener(handler1, handler2)
    opener3.addheaders = [
        ('User-agent' , 'Mozilla/5.0'),
        ('Host' , urlinfo.netloc)
    ]
    response = opener3.open(request, timeout=20.0)

    if not os.path.isdir(TMP_DIR):
        os.mkdir(TMP_DIR)

    # write a temporary file in the original encoding
    tmp = tempfile.mktemp(dir=TMP_DIR)
    f = open(tmp, 'wb')
    shutil.copyfileobj(response, f, BLOCKSIZE)
    ctype = response.headers.get('content-type', '').split(';')[0].strip()
    response.close()
    f.close()

    charset = guess_charset(response, tmp)

    tmp2 = tempfile.mktemp(dir=TMP_DIR)
    reencode(tmp, charset, tmp2, 'utf-8')

    f = gp_open(tmp2)
    body = f.read()
    f.close()

    os.remove(tmp)
    os.remove(tmp2)

    return (ctype, body)


def reencode(src_path, src_encoding, dest_path, dest_encoding):
    src_file = codecs.open(src_path, "r", src_encoding)
    dest_file = codecs.open(dest_path, "w", dest_encoding)
    shutil.copyfileobj(src_file, dest_file, BLOCKSIZE)
    src_file.close()
    dest_file.close()


def url_to_text(url):
    (content_type, body) = download_url(url)
    lurl = url.lower()
    if 'html' in content_type or lurl.endswith('.html'):
        return html_to_text(body)
    elif 'xml' in content_type or lurl.endswith('.xml'):
        return xml_to_text(body)
    elif 'text/plain' in content_type or lurl.endswith('.txt'):
        return text_to_text(body)
    else:
        return None


def html_to_text(html):
    soup = BeautifulSoup(html.encode('utf-8'), from_encoding='utf-8')
    return soup.get_text(' ')


def text_to_text(txt):
    return txt


def xml_to_text(xml):
    soup = BeautifulSoup(xml.encode('utf-8'), 'xml', from_encoding='utf-8')
    return soup.get_text(' ')


def test_download_url():
    me = download_url('http://www.shilad.com')
    assert(me[0] == 'text/html')
    assert(me[1].startswith('<!doctype'))
    assert('Shilad' in me[1])

def test_url_to_text():
    text = url_to_text('http://www.shilad.com')
    assert(text.strip().startswith('Shilad Sen'))