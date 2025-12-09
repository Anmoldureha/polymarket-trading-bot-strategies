
import unittest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

from src.strategies.tail_end_strategy import TailEndStrategy
from src.strategies.combinatorial_arbitrage import CombinatorialStrategy

class TestNewStrategies(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_risk_manager = MagicMock()
        self.mock_market_cache = MagicMock()
        self.config = {}

    def test_tail_end_strategy(self):
        strategy = TailEndStrategy(
            name="tail_end",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config={'min_price': 0.90, 'max_price': 0.99, 'max_days_to_expiry': 7},
            market_cache=self.mock_market_cache
        )
        
        # Mock Markets
        future_date = (datetime.utcnow() + timedelta(days=3)).isoformat()
        far_date = (datetime.utcnow() + timedelta(days=20)).isoformat()
        
        markets = [
            {'id': 'm1', 'question': 'Will X happen?', 'end_date_iso': future_date, 'tokens': [{'token_id': 't1', 'outcome': 'YES'}]},
            {'id': 'm2', 'question': 'Will Y happen?', 'end_date_iso': far_date, 'tokens': [{'token_id': 't2', 'outcome': 'YES'}]}
        ]
        self.mock_market_cache.get_markets.return_value = markets
        
        # Mock Prices
        # m1: YES @ 0.95 (Match)
        self.mock_market_cache.get_price.side_effect = lambda mid, outcome: {'ask': 0.95} if mid == 'm1' else {'ask': 0.50}
        
        opportunities = strategy.scan_opportunities()
        
        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0]['market_id'], 'm1')
        self.assertEqual(opportunities[0]['price'], 0.95)
        print("✅ Tail End Strategy verified")

    def test_combinatorial_strategy(self):
        strategy = CombinatorialStrategy(
            name="combinatorial",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config={'keywords': ['Bitcoin'], 'divergence_threshold': 0.10},
            market_cache=self.mock_market_cache
        )
        
        # Mock Markets (Correlated)
        markets = [
            {'id': 'm1', 'question': 'Will Bitcoin hit 100k?', 'keywords': 'Bitcoin'},
            {'id': 'm2', 'question': 'Will Bitcoin hit 100k in 2024?', 'keywords': 'Bitcoin'}
        ]
        self.mock_market_cache.get_markets.return_value = markets
        
        # Mock Prices (Divergent)
        # m1: YES @ 0.40, m2: YES @ 0.50 (Diff 0.10, 20% > 10%)
        self.mock_market_cache.get_price.side_effect = lambda mid, outcome: {'ask': 0.40} if mid == 'm1' else {'ask': 0.50}
        
        opportunities = strategy.scan_opportunities()
        
        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0]['type'], 'divergence')
        self.assertAlmostEqual(opportunities[0]['diff'], 0.10)
        print("✅ Combinatorial Strategy verified")

if __name__ == '__main__':
    unittest.main()
