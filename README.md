# geo-provenance

This project contains tools for geocoding the *geoprovenance* of webresources.
A web page's geoprovenance is the home country for the original publisher of the information contained in the web page.
For a web resource created by a company or organization, this would be the headquarters of the country.
For an individual author, it would that individual's home country.
For a book, it would be the country associated with the publisher of the book.

More details are provided in our [2015 CHI paper](http://www-users.cs.umn.edu/~bhecht/publications/localnessgeography_CHI2015.pdf). If you use this software in an academic publication, please cite it as follows: Sen, S., Ford, H., Musicant, D., Graham, M., Keyes, O., and Hecht, B. 2015. "Barriers to the Localness of Volunteered Geographic Information." *Proceedings of CHI 2015.* New York: ACM Press.

### Using this Library

Warning: Ability to code new URLs awaiting whois scripts from Dave Musicant.


### The GeoProv198 Dataset

The logistic regression classification model used in this package is trained using a gold standard dataset that maps urls to countries. This dataset is available in the [data](https://github.com/shilad/geo-provenance/blob/master/data/geoprov198.tsv) directory and its collection methodology is described in the citation above.

### Credits

* Shilad Sen developed the geoprovenance inference algorithm and software.
* Dave Musicant developed the code to extract country names from whois queries.
* Heather Ford led development of GeoProv198, with major assistance from Brent Hecht and minor assistance from Dave Musicant, Shilad Sen, and Mark Graham.
