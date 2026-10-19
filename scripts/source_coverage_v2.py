"""Unverified historical FIFA roster coverage labels shared by V2 export and QA.

A numerically complete PES estimate is not evidence that the source contained
every player available in a particular FIFA release or snapshot.
"""
FIFAINDEX_PROVIDER = "lbenz730/fifa_model"
KNOWN_SCRAPE_PAGE_COUNT = 700
OBSERVED_FIFAINDEX_PAGE_CEILING = 10500


def source_coverage_status(edition, rows, provider):
    if edition == 2025:
        return "EXCLUDED_FC25_NOT_CONVERTED"
    if (2005 <= edition <= 2020
            and provider == FIFAINDEX_PROVIDER
            and rows == OBSERVED_FIFAINDEX_PAGE_CEILING):
        return "KNOWN_SCRAPER_PAGE_LIMIT_REACHED_COVERAGE_UNVERIFIED"
    return "SOURCE_COVERAGE_NOT_INDEPENDENTLY_VERIFIED"
