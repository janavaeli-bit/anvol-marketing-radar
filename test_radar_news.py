import unittest
from unittest.mock import patch
from types import SimpleNamespace
import pandas as pd
from radar_news import NEWS_COLUMNS, collect, feed_url, recent_rows, read_feed

NOW = pd.Timestamp('2026-11-09T12:00:00Z')


def row(title, date, market='Sweden'):
    return dict(zip(NEWS_COLUMNS, [date, title, market, 'Collectibles', 'High',
                                  'viral toy', 'Example', 'https://example.com']))


class FreshnessTests(unittest.TestCase):
    def test_old_missing_invalid_and_future_dates_excluded(self):
        rows = [row('Current', 'Mon, 09 Nov 2026 10:00:00 GMT'),
                row('Boundary', '2026-11-02T12:00:00Z'),
                row('March', '2026-03-01'), row('Missing', ''),
                row('Invalid', 'not a date'), row('Future', '2026-11-10')]
        df, excluded = recent_rows(rows, NEWS_COLUMNS, 7, NOW)
        self.assertEqual(df.Headline.tolist(), ['Current', 'Boundary'])
        self.assertEqual(excluded, 4)

    def test_deduplication_retains_different_markets(self):
        rows = [row('New Toy!', '2026-11-09T10:00:00Z'),
                row('new toy', '2026-11-08T10:00:00Z'),
                row('New Toy!', '2026-11-09T10:00:00Z', 'Finland')]
        df, _ = recent_rows(rows, NEWS_COLUMNS, 7, NOW)
        self.assertEqual(len(df), 2)
        self.assertEqual(set(df.Market), {'Sweden', 'Finland'})

    def test_empty_results_have_display_columns(self):
        df, excluded = recent_rows([], NEWS_COLUMNS, 7, NOW)
        self.assertTrue(df.empty)
        self.assertIn('Age (days)', df)
        self.assertEqual(excluded, 0)

    def test_local_editions_and_query_window(self):
        self.assertIn('when%3A7d', feed_url('LEGO', 'Sweden'))
        self.assertIn('ceid=SE:sv', feed_url('LEGO', 'Sweden'))
        self.assertIn('ceid=FI:fi', feed_url('LEGO', 'Finland'))

    def test_one_failed_feed_does_not_hide_successful_feed(self):
        queries = pd.DataFrame([{'Query': q, 'Market': 'Sweden',
                                'Category': 'Collectibles', 'Priority': 'High'}
                               for q in ['good', 'bad']])
        def reader(url):
            if 'bad' in url:
                raise TimeoutError('test timeout')
            return SimpleNamespace(entries=[{'title': 'Current launch',
                'published': 'Mon, 09 Nov 2026 10:00:00 GMT', 'link': 'https://example.com'}])
        df, status = collect(queries, reader=reader, now=NOW)
        self.assertEqual(len(df), 1)
        self.assertEqual(status['successful'], 1)
        self.assertEqual(len(status['errors']), 1)
        self.assertIsNotNone(status['last_success'])
        _, failed = collect(queries.tail(1), reader=reader, now=NOW)
        self.assertIsNone(failed['last_success'])

    def test_valid_empty_feed_is_success(self):
        queries = pd.DataFrame([{'Query': 'toy', 'Market': 'Sweden',
                                'Category': 'Collectibles', 'Priority': 'High'}])
        df, status = collect(queries, reader=lambda _: SimpleNamespace(entries=[]), now=NOW)
        self.assertTrue(df.empty)
        self.assertEqual(status['successful'], 1)
        self.assertEqual(status['errors'], [])

    def test_bad_xml_is_reported_as_failure(self):
        from io import BytesIO
        with patch('radar_news.urlopen', return_value=BytesIO(b'<html>unavailable</html>')):
            with self.assertRaises(ValueError):
                read_feed('https://example.com')


if __name__ == '__main__':
    unittest.main()
