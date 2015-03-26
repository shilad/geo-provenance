#!/usr/bin/python
#
# Reads URLs from stdin and writes inferred countries to stdout.
# The result is a json-formatted dictionary of country-code -> probability pairs.
#


import json
import sys
import time
import traceback

from gputils import *
from gpinfer import LogisticInferrer
from pagelang import OnlinePagelangProvider


def main(inferrer, input, output, known_domains=None):
    for line in input:
        url = line.split()[0]
        if not url:
            continue
        d = url2registereddomain(url)
        if known_domains and d not in known_domains:
            continue
        try:
            (conf, dist) = inferrer.infer(url)
            output.write(url + '\t' + json.dumps(dist) + '\n')
            output.flush()
        except:
            warn('url %s failed: ' + url)
            traceback.print_exc()
        time.sleep(10)

if __name__ == '__main__':

    # use the full dataset
    set_feature_dir(DATA_DIR + '/features')

    inferrer = LogisticInferrer()
    pl = inferrer.get_feature('pagelang')
    pl.page_provider = OnlinePagelangProvider(pl.page_provider)

    f = gp_open(get_feature_data_path('whois'))
    known_domains = set(l.split()[0] for l in f)
    f.close()

    main(inferrer, sys.stdin, sys.stdout, known_domains)