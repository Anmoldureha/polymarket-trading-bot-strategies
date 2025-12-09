
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

from src.strategies.tail_end_strategy import TailEndStrategy
from src.strategies.combinatorial_arbitrage import CombinatorialStrategy
from src.strategies.market_making import MarketMakingStrategy

class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_risk_manager = MagicMock()
        self.mock_market_cache = MagicMock()
        self.config = {}

    # --- Tail End Strategy Edge Cases ---

    def test_tail_end_invalid_date(self):
        """Test scanning with markets having invalid or missing dates"""
        strategy = TailEndStrategy(
            name="tail_end",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config={'min_price': 0.90},
            market_cache=self.mock_market_cache
        )
        
        # Market with invalid date
        markets = [
            {'id': 'm1', 'end_date_iso': 'not-a-date', 'tokens': [{'token_id': 't1', 'outcome': 'YES'}]},
            {'id': 'm2', 'end_date_iso': None, 'tokens': [{'token_id': 't2', 'outcome': 'YES'}]}
        ]
        self.mock_market_cache.get_markets.return_value = markets
        
        # Should not crash, just return empty list
        opportunities = strategy.scan_opportunities()
        self.assertEqual(len(opportunities), 0)
        print("✅ Tail-End: Handled invalid dates gracefully")

    def test_tail_end_price_zero(self):
        """Test scanning where price is 0 (illiquid/error)"""
        strategy = TailEndStrategy(
            name="tail_end",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config={'min_price': 0.90},
            market_cache=self.mock_market_cache
        )
        
        future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
        markets = [{'id': 'm1', 'end_date_iso': future_date, 'tokens': [{'token_id': 't1', 'outcome': 'YES'}]}]
        self.mock_market_cache.get_markets.return_value = markets
        
        # Price is 0 or None
        self.mock_market_cache.get_price.return_value = {'ask': 0}
        
        opportunities = strategy.scan_opportunities()
        self.assertEqual(len(opportunities), 0)
        print("✅ Tail-End: Handled zero price gracefully")

    # --- Combinatorial Strategy Edge Cases ---

    def test_combinatorial_empty_keywords(self):
        """Test with no keywords configured"""
        strategy = CombinatorialStrategy(
            name="combinatorial",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config={'keywords': []},
            market_cache=self.mock_market_cache
        )
        
        markets = [{'id': 'm1', 'question': 'Bitcoin'}]
        self.mock_market_cache.get_markets.return_value = markets
        
        opportunities = strategy.scan_opportunities()
        self.assertEqual(len(opportunities), 0)
        print("✅ Combinatorial: Handled empty keywords gracefully")

    def test_combinatorial_zero_prices(self):
        """Test validation to prevent division by zero"""
        strategy = CombinatorialStrategy(
            name="combinatorial",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config={'keywords': ['Bitcoin']},
            market_cache=self.mock_market_cache
        )
        
        markets = [
            {'id': 'm1', 'question': 'Bitcoin 1'},
            {'id': 'm2', 'question': 'Bitcoin 2'}
        ]
        self.mock_market_cache.get_markets.return_value = markets
        
        # Both prices 0
        self.mock_market_cache.get_price.return_value = {'ask': 0.0}
        
        opportunities = strategy.scan_opportunities()
        self.assertEqual(len(opportunities), 0)
        print("✅ Combinatorial: Handled zero prices (div by zero check)")

    def test_combinatorial_similarity_empty_strings(self):
        """Test similarity calculation with empty strings"""
        strategy = CombinatorialStrategy(
            name="combinatorial",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config={},
            market_cache=self.mock_market_cache
        )
        
        score = strategy._calculate_similarity("", "Bitcoin")
        self.assertEqual(score, 0.0)
        
        score = strategy._calculate_similarity(None, "Bitcoin")
        self.assertEqual(score, 0.0)
        print("✅ Combinatorial: Handled empty similarity strings")

    # --- Market Making Strategy Edge Cases ---

    def test_market_making_malformed_dates(self):
        """Test age filtering with malformed dates"""
        # Need to fix the import inside the method in market_making.py or mock it? 
        # The import is inside scan_opportunities, so simulation should work.
        
        strategy = MarketMakingStrategy(
            name="market_making",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config={'enabled': True, 'max_age_hours': 24},
            market_cache=self.mock_market_cache
        )
        
        # Market with malformed date
        markets = [{'id': 'm1', 'created_at': 'invalid-date', 'market_id': 'm1'}]
        self.mock_market_cache.get_markets.return_value = markets
        self.mock_market_cache.get_price.return_value = {'bid': 0.5, 'ask': 0.55}
        
        # Should catch exception and NOT filter it out (fail open or closed? code says pass -> checks price)
        # If it passes date check due to error, it proceeds to check price.
        
        opportunities = strategy.scan_opportunities()
        # If it processed the market despite invalid date, it should check 'update_interval' and maybe add it
        # Since last_update is 0, it should add it if it reaches that point.
        
        self.assertEqual(len(opportunities), 1)
        print("✅ Market Making: Handled malformed dates (Fail Open)")

if __name__ == '__main__':
    unittest.main()
