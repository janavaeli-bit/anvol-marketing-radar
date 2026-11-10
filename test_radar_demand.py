import unittest
from unittest.mock import Mock
from types import SimpleNamespace
import pandas as pd
from radar_demand import DemandStore, trends_url


class DemandTests(unittest.TestCase):
    def setUp(self):
        self.now = 100000
        self.loader = Mock(return_value=pd.DataFrame({'LEGO': [10, 20]}))
        self.store = DemandStore(self.loader, lambda: self.now)

    def test_no_request_without_explicit_load(self):
        self.store.get(['LEGO'], 'SE')
        self.loader.assert_not_called()

    def test_cached_success_shared_across_same_comparisons(self):
        self.store.get(['LEGO', 'Barbie'], 'SE', request=True)
        self.store.get(['Barbie', 'LEGO'], 'SE', request=True)
        self.assertEqual(self.loader.call_count, 1)

    def test_429_pauses_requests_across_markets_then_allows_retry(self):
        exc = RuntimeError('HTTP 429')
        exc.response = SimpleNamespace(status_code=429)
        self.loader.side_effect = exc
        result = self.store.get(['LEGO'], 'SE', request=True)
        self.assertIn('429', result['error'])
        self.assertEqual(result['retry_seconds'], 900)
        self.now += 100
        self.store.get(['LEGO'], 'FI', request=True)
        self.assertEqual(self.loader.call_count, 1)
        self.now += 801
        self.loader.side_effect = None
        self.assertIsNotNone(self.store.get(['LEGO'], 'SE', request=True)['data'])
        self.assertEqual(self.loader.call_count, 2)

    def test_failed_refresh_preserves_and_labels_stale_data(self):
        self.store.get(['LEGO'], 'SE', request=True)
        self.now += 21601
        self.loader.side_effect = RuntimeError('429')
        result = self.store.get(['LEGO'], 'SE', request=True)
        self.assertTrue(result['stale'])
        self.assertIsNotNone(result['data'])
        self.assertIsNotNone(result['fetched_at'])

    def test_new_market_never_displays_other_markets_data(self):
        self.store.get(['LEGO'], 'SE', request=True)
        result = self.store.get(['LEGO'], 'FI')
        self.assertIsNone(result['data'])
        self.assertIsNone(result['fetched_at'])

    def test_old_snapshot_expires_and_empty_response_is_not_failure(self):
        self.loader.return_value = pd.DataFrame()
        result = self.store.get(['LEGO'], 'SE', request=True)
        self.assertIsNone(result['error'])
        self.assertIsNotNone(result['fetched_at'])
        self.now += 86401
        self.assertIsNone(self.store.get(['LEGO'], 'SE')['fetched_at'])

    def test_success_cache_does_not_expose_mutable_data(self):
        result = self.store.get(['LEGO'], 'SE', request=True)
        result['data'].iloc[0, 0] = 99
        self.assertEqual(self.store.get(['LEGO'], 'SE')['data'].iloc[0, 0], 10)

    def test_google_link_preserves_market_and_terms(self):
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(trends_url(['Pokémon', 'LEGO'], 'SE')).query)
        self.assertEqual(query['geo'], ['SE'])
        self.assertEqual(query['q'], ['Pokémon,LEGO'])


if __name__ == '__main__':
    unittest.main()
