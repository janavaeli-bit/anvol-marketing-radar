"""Bound Google Trends requests and retain successful comparisons in memory."""
from datetime import datetime, timezone
from threading import RLock
from time import time
from math import ceil
from urllib.parse import urlencode


def trends_url(keywords, geo):
    return 'https://trends.google.com/trends/explore?' + urlencode(
        {'date': 'today 3-m', 'geo': geo, 'q': ','.join(keywords)})


def load_google_trends(keywords, geo):
    from pytrends.request import TrendReq
    # No automatic retries: repeated requests can prolong a provider rate limit.
    connector = TrendReq(hl='en-US', tz=0, timeout=(10, 25), retries=0)
    connector.build_payload(list(keywords), timeframe='today 3-m', geo=geo)
    frame = connector.interest_over_time()
    if frame is not None and 'isPartial' in frame:
        frame = frame.loc[~frame['isPartial'].fillna(False).astype(bool)].drop(columns='isPartial')
    return frame


class DemandStore:
    def __init__(self, loader=load_google_trends, clock=time):
        self.loader, self.clock = loader, clock
        self.lock = RLock()
        self.cache = {}
        self.next_request_at = 0
        self.last_error = None

    def get(self, keywords, geo, request=False):
        terms = tuple(sorted({str(k).strip() for k in keywords if str(k).strip()}))
        if not 1 <= len(terms) <= 5:
            raise ValueError('Select between one and five keywords.')
        key = (geo, terms)
        with self.lock:
            now = self.clock()
            stored = self.cache.get(key)
            fresh = stored is not None and now - stored[1] < 21600
            error = None
            if request and not fresh and now >= self.next_request_at:
                try:
                    frame = self.loader(terms, geo)
                    fetched = self.clock()
                    self.cache[key] = (frame.copy() if frame is not None else None, fetched)
                    if len(self.cache) > 128:
                        oldest = min(self.cache, key=lambda k: self.cache[k][1])
                        del self.cache[oldest]
                    self.next_request_at = fetched + 30
                    self.last_error = None
                    stored, fresh = self.cache[key], True
                except Exception as exc:
                    status = getattr(getattr(exc, 'response', None), 'status_code', None)
                    limited = status == 429 or '429' in str(exc)
                    error = ('Google Trends is temporarily limiting requests (429). '
                             'The app will pause new requests for 15 minutes.' if limited else
                             'Google Trends could not be reached. Please try again later.')
                    self.last_error = error
                    self.next_request_at = self.clock() + (900 if limited else 60)
            remaining = max(0, ceil(self.next_request_at - self.clock()))
            if not fresh and remaining:
                error = self.last_error or 'Please pause briefly between new comparisons.'
            frame, fetched = stored if stored is not None else (None, None)
            if stored is not None and self.clock() - fetched > 86400:
                frame, fetched = None, None
            return {'data': frame.copy() if frame is not None else None,
                    'fetched_at': datetime.fromtimestamp(fetched, timezone.utc).isoformat() if fetched is not None else None,
                    'stale': fetched is not None and not fresh,
                    'error': error, 'retry_seconds': remaining,
                    'url': trends_url(terms, geo)}
