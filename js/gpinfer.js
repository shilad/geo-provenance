var GP = window.GP || {};

String.prototype.endsWith = function(suffix) {
    return this.indexOf(suffix, this.length - suffix.length) !== -1;
};

GP.testUsingConsole = function(url) {
    console.log('testing inferrence of url ' + url);
    console.log('domain is ' + GP.getDomain(url));
    console.log('registered domain is ' + GP.getRegisteredDomain(url));
    GP.LogisticInferrer(url,
            function (result) {
                console.log('result', JSON.stringify(result));
                if (result[0] == 'final') {
                    var dist = result[1];
                    var countries = Object.keys(dist).sort(function(a,b){return dist[b]-dist[a];})
                    console.log('most likely countries:');
                    for (var i = 0; i < countries.length && i < 10; i++) {
                        var c = countries[i];
                        var p = dist[c];
                        console.log('\t' + c + ': ' + p);
                    }
                }
            },
            function (msg) { console.log('message', JSON.stringify(msg))},
            function (err) { console.log('error', JSON.stringify(err))}
        );
};

GP.LogisticInferrer = function (url, onResult, onMessage, onError) {
    var inferrers = {
        'tld' : GP.TLDInferrer,
        'wikidata' : GP.WikiDataInferrer,
        'ip' : GP.IPInferrer,
        'whois' : GP.WhoIsInferrer,
        'lang' : GP.PageLangInferrer,
        'prior' : GP.PriorInferrer
    };
    var coefficients = {
        'intercept' : -7.06,
        'prior'     : 2.38,
        'parsed'    : 5.39,
        'freetext'  : 2.06,
        'wikidata'  : 2.03,
        'lang'      : 5.37,
        'tld'       : 7.03
    };

    var logistic = function(x) { return 1.0 / (1.0 + Math.exp(-x)); };
    var dists = {};

    var receivedResult = function(name, result) {
        dists[name] = result;
        var need = Object.keys(inferrers).length;
        var have = Object.keys(dists).length;
        if (need != have) {
            onMessage(['final', 'awaiting results from ' + (need-have) + ' more inferrer(s).']);
            return; // awaiting more results from sub-inferrerrs!
        }
        onMessage(['final', 'recevied all inferrer results.']);

        var results = {};
        GP_COUNTRIES.forEach(function (c) { results[c.iso] = coefficients.intercept; })
        for (var k in coefficients) {
            if (!dists[k]) continue;
            for (var c in dists[k]) {
                if (!results[c]) continue;
                results[c] += dists[k][c] * coefficients[k];
            }
        }
        var sum = 0.0;
        for (var c in results) {
            var p = logistic(results[c]);
            p = Math.pow(p, 1.2);   // to calibrate probabilities
            results[c] = p;
            sum += p;
        }

        for (var c in results) {
            results[c] /= sum;
        }
        onResult(['final', results]);
    };

    $.each(inferrers, function (name, fn) {
        fn(
            url,
            function (result) { onResult([name, result]); receivedResult(name, result); },
            function (msg) { onMessage([name, msg]); },
            function (err) { onError([name, err]); receivedResult(name, {}); }
        );
    });

};

GP.PriorInferrer = function (url, onResult, onMessage, onError) {
    var dist = {};
    GP_COUNTRIES.forEach(function (c) { dist[c.tld] = c.prior; });
    onResult(dist);
};

GP.TLDInferrer = function (url, onResult, onMessage, onError) {
    var domain = GP.getDomain(url);
    var iso = null;
    if (domain.endsWith('.mil') || domain.endsWith('.gov')) {
        onMessage('tld corresponds to US military or government domain.');
        iso = 'us';
    } else {
        GP_COUNTRIES.forEach(function (c) {
            if (domain.endsWith('.' + c.tld)) {
                iso = c.iso;
            }
        });
    }
    onResult(GP.countryToDist(iso));
};

GP.WikiDataInferrer = function (url, onResult, onMessage, onError) {
    var domain = GP.getRegisteredDomain(url);
    var coords = GP_WIKIDATA_COORDS[domain];
    if (coords) {
        onMessage('Geocoding country for wikidata organization coordinates (' + coords + ')...');
        var tokens = coords.split(',');
        $.ajax({
            method: "GET",
            url: "http://nominatim.openstreetmap.org/reverse?",
            dataType: 'json',
            data: { format: "json", lat: tokens[0], lon: tokens[1] }
        }).done(function (data) {
                if (data && data.address && data.address.country_code) {
                    onResult(GP.countryToDist(data.address.country_code));
                } else {
                    onError('Unexpected wikidata geocoding response: ' + data);
                }
            }
        ).fail(function (msg) {
                onError('Wikidata geocoding failed: ' + msg);
            });
    } else {
        onMessage('No wikidata coordinates found for url');
        onResult({});
    }
};

GP.IPInferrer = function (url, onResult, onMessage, onError) {
    var domain = GP.getDomain(url);
    onMessage('Geocoding server hostname...');
    $.ajax({
        method: "GET",
        url: "http://freegeoip.net/json/" + domain,
        dataType: 'json'
    }).done(function (data) {
            if (data && data.country_code) {
                onResult(GP.countryToDist(data.country_code));
            } else {
                onError('Unexpected server geocoding response: ' + data);
            }
        }
    ).fail(function (msg) {
            onError('Wikidata geocoding failed: ' + msg);
        });
};

GP.WhoIsInferrer = function (url, onResult, onMessage, onError) {
    var domain = GP.getRegisteredDomain(url);
    var escapeRegExp = function(str) {
        return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, "\\$&");
    };

    onMessage('Queuing whois query for ' + domain);

    return onResult(['freetext', { us : 1.0 }]);

    $.ajax({
        method: "GET",
        url: "http://www.whoisxmlapi.com/whoisserver/WhoisService?domainName=" + domain + "&outputFormat=json",
        dataType: 'jsonp'
    }).done(function (data) {
        if (!data || !data.WhoisRecord || !data.WhoisRecord.registryData) {
            return onError('unexpected whois response: ' + JSON.stringify(data));
        }
        var nodes = [data.WhoisRecord, data.WhoisRecord.registryData];

        for (var i = 0; i < nodes.length; i++) {
            var response = nodes[i];
            if (response.administrativeContact && response.administrativeContact.country) {
                var dist = GP.countryToDist(response.administrativeContact.country);
                if (dist) {
                    return onResult(['parsed', dist]);
                }
            }
        }

        for (var i = 0; i < nodes.length; i++) {
            var response = nodes[i];
            for (var key in response) {
                var val = response[key];
                if (typeof(val) == 'object' && val.country) {
                    var dist = GP.countryToDist(val.country);
                    if (dist) {
                        return onResult(['parsed', dist]);
                    }
                }
            }
        }

        onMessage('Structured parsing for whois record failed... attempting freetext parsing');

        for (var i = 0; i < nodes.length; i++) {
            var response = nodes[i];

            var text = response.rawText.toLowerCase();
            var words = {};
            text.split(/\s+/).forEach(function (w) {
                words[w] = true;
            });

            var total = 0;
            var dist = {};
            for (var alias in GP_ALIASES) {
                var parts = alias.split(/\s+/);
                var isCandidate = parts.every(function (p) {
                    return words[p];
                });
                if (isCandidate) {
                    var re = "(^|\\s)(" + escapeRegExp(alias) + ")($|\\s)";
                    var m = text.match(new RegExp(re, "g"));
                    if (m) {
                        var iso = GP_ALIASES[alias];
                        onMessage('In whois record, found alias ' + alias + ' for country ' + iso);
                        if (!(iso in dist)) dist[iso] = 0;
                        dist[iso] += m.length;
                        total += m.length;
                    }
                }
            }
            for (var c in dist) {
                dist[c] /= 1.0 * total;
            }
            onResult(['freetext', dist]);
        }
    }).fail(function (msg) {
        onError('Whois lookup failed: ' + msg);
    });

};
GP.PageLangInferrer = function (url, onResult, onMessage, onError) {
    var jsEscape = function (string) {
        return ('' + string).replace(/["'\\\n\r\u2028\u2029]/g, function (character) {
            // Escape all characters not included in SingleStringCharacters and
            // DoubleStringCharacters on
            // http://www.ecma-international.org/ecma-262/5.1/#sec-7.8.4
            switch (character) {
                case '"':
                case "'":
                case '\\':
                    return '\\' + character
                // Four possible LineTerminator characters need to be escaped:
                case '\n':
                    return '\\n'
                case '\r':
                    return '\\r'
                case '\u2028':
                    return '\\u2028'
                case '\u2029':
                    return '\\u2029'
            }
        })
    };

    var yql = "select * from html where url = '" + jsEscape(url) + "'";
    var yql_url = 'http://query.yahooapis.com/v1/public/yql?' + $.param({q : yql}) ;

    var xhr = createCORSRequest('GET', yql_url);
    if (!xhr) {
        return onError('CORS not supported');
    }
    xhr.onload = function() {
        var responseText = xhr.responseText;
        var stripped = responseText.replace(/(<([^>]+)>)/ig,"").replace(/  +/g, ' ');
        guessLanguage.detect(stripped, function(language) {
            if (!language) {
                return onError("No language inferred for URL.");
            } else {
                onMessage("Inferred language " + language);
                if (!GP_LANG_TO_COUNTRY[language.toLowerCase()]) {
                    return onError("Unknown language inferred for URL: " + language);
                } else {
                    var dist = {};
                    GP_LANG_TO_COUNTRY[language.toLowerCase()].forEach(function (pair) {
                        var iso = pair[0];
                        var prob = pair[1];
                        dist[iso] = prob;
                    });
                    return onResult(dist);
                }
            }
        });
    };
    xhr.onerror = function() {
        return onError('An error occurred when retrieving the html of ' + url);
    };
    onMessage('retriving html to detect language of url ' + url);
    xhr.send();
};

GP.getDomain = function(url) {
    var parser = document.createElement('a');
    parser.href = url;
    return parser.hostname;
};

GP.getRegisteredDomain = function(url) {
    var domain = GP.getDomain(url);
    return RegDomain.getRegisteredDomain(domain).toLowerCase();
};

GP.countryToDist = function (country) {
    country = (!country) ? '' : country.toLowerCase();
    var iso = null;
    if (country.length < 2) {
        // invalid
    } else if (country.length == 2) {
        iso = country;
    } else if (country in GP_ALIASES) {
        iso = GP_ALIASES[country];
    }
    if (iso) {
        var dist = {};
        dist[iso] = 1.0;
        return dist;
    } else {
        return {};
    }
};

/**
 * From http://www.html5rocks.com/en/tutorials/cors/
 * @param method
 * @param url
 * @returns {XMLHttpRequest}
 */
function createCORSRequest(method, url) {
    var xhr = new XMLHttpRequest();
    if ("withCredentials" in xhr) {

        // Check if the XMLHttpRequest object has a "withCredentials" property.
        // "withCredentials" only exists on XMLHTTPRequest2 objects.
        xhr.open(method, url, true);

    } else if (typeof XDomainRequest != "undefined") {

        // Otherwise, check if XDomainRequest.
        // XDomainRequest only exists in IE, and is IE's way of making CORS requests.
        xhr = new XDomainRequest();
        xhr.open(method, url);

    } else {

        // Otherwise, CORS is not supported by the browser.
        xhr = null;

    }
    return xhr;
}