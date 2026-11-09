"""Date-aware public news collection, independent of the dashboard UI."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import re

import feedparser
import pandas as pd

NEWS_COLUMNS = ['Published', 'Headline', 'Market', 'Category', 'Priority',
                'Search signal', 'Source', 'Link']
SOCIAL_COLUMNS = ['Published', 'Headline', 'Platform', 'Category', 'Priority',
                  'Watch term', 'Source', 'Link']


def feed_url(term, market=None, days=7):
    # Use supported local editions; retain English discovery for global/Baltic queries.
    hl, gl, ceid = {'Sweden': ('sv', 'SE', 'SE:sv'),
                    'Finland': ('fi', 'FI', 'FI:fi')}.get(market, ('en', 'US', 'US:en'))
    query = quote_plus(f'{term} when:{int(days)}d')
    return f'https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}'


def read_feed(url):
    request = Request(url, headers={'User-Agent': 'AnvolMarketingRadar/1.1'})
    with urlopen(request, timeout=15) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError('Feed exceeds size limit')
    feed = feedparser.parse(raw)
    if feed.get('bozo') or not feed.get('version'):
        raise ValueError('Invalid news feed')
    return feed


def recent_rows(rows, columns, days, now=None):
    """Validate dates locally; query time restrictions alone are insufficient."""
    df = pd.DataFrame(rows, columns=columns)
    current = pd.Timestamp(now if now is not None else datetime.now(timezone.utc))
    current = current.tz_localize('UTC') if current.tzinfo is None else current.tz_convert('UTC')
    dates = pd.to_datetime(df['Published'], utc=True, errors='coerce', format='mixed')
    valid = dates.notna() & dates.ge(current - pd.Timedelta(days=days)) & dates.le(current)
    excluded = int((~valid).sum())
    df = df.loc[valid].copy()
    df['Published'] = dates.loc[valid]
    df['Age (days)'] = ((current - df['Published']).dt.total_seconds() / 86400).round(1)
    df['_title'] = df['Headline'].map(lambda x: re.sub(r'\W+', ' ', str(x).casefold()).strip())
    # Keep market attribution: one story can matter in several countries.
    keys = ['_title', 'Market'] if 'Market' in df else ['_title']
    df = df.sort_values('Published', ascending=False).drop_duplicates(keys).drop(columns='_title')
    return df, excluded


def collect(queries, days=7, social=False, reader=read_feed, now=None):
    rows, errors, successful_times = [], [], []
    attempted = 0
    jobs = []
    for _, query in queries.iterrows():
        term = str(query['Query'])
        searches = [('News', term)] if not social else [
            ('YouTube coverage', f'site:youtube.com {term}'),
            ('TikTok coverage', f'site:tiktok.com {term}'),
            ('Social news coverage', f'{term} viral trend')]
        for platform, search in searches:
            jobs.append((query, term, platform, search))
    attempted = len(jobs)
    def retrieve(job):
        query, term, platform, search = job
        try:
            return reader(feed_url(search, query.get('Market'), days))
        except Exception as exc:
            return exc
    with ThreadPoolExecutor(max_workers=8) as pool:
        for (query, term, platform, search), result in zip(jobs, pool.map(retrieve, jobs)):
            if isinstance(result, Exception):
                errors.append(f'{term} ({platform}): {type(result).__name__}: {result}')
                continue
            try:
                feed = result
                successful_times.append(datetime.now(timezone.utc).isoformat())
                # Filter all returned entries before selecting any UI highlights.
                for entry in feed.entries:
                    source = entry.get('source', {})
                    row = {'Published': entry.get('published', ''),
                           'Headline': entry.get('title', ''),
                           'Category': query['Category'], 'Priority': query['Priority'],
                           'Source': source.get('title', 'Google News') if isinstance(source, dict) else 'Google News',
                           'Link': entry.get('link', '')}
                    if social:
                        row.update({'Platform': platform, 'Watch term': term})
                    else:
                        row.update({'Market': query['Market'], 'Search signal': term})
                    rows.append(row)
            except Exception as exc:
                errors.append(f'{term} ({platform}): {type(exc).__name__}: {exc}')
    frame, excluded = recent_rows(rows, SOCIAL_COLUMNS if social else NEWS_COLUMNS, days, now)
    return frame, {'attempted': attempted, 'successful': len(successful_times),
                   'last_success': max(successful_times) if successful_times else None,
                   'excluded': excluded, 'errors': errors}
