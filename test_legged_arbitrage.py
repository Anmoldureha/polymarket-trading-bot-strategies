
import unittest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
import sys
import os

sys.path.insert(0, os.path.abspath("src"))
from src.strategies.legged_arbitrage import LeggedArbitrageStrategy

@dataclass
class MockPosition:
    id: str
    market_id: str
    outcome: str
    average_price: float
    size: float
    timestamp: float

class TestLeggedArbitrage(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_risk_manager = MagicMock()
        self.mock_market_cache = MagicMock()
        self.config = {
            'keywords': ['Bitcoin'],
            'entry_max_price': 0.30,
            'max_total_cost': 0.95
        }
        
    def test_entry_scan(self):
        """Test finding new entry opportunities"""
        strategy = LeggedArbitrageStrategy(
            name="legged",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config=self.config,
            market_cache=self.mock_market_cache
        )
        
        # Mock Market: Bitcoin
        market = {'id': 'm1', 'question': 'Will Bitcoin hit 100k?'}
        self.mock_market_cache.get_markets.return_value = [market]
        
        # Mock Price: NO is cheap (0.25)
        self.mock_client.get_best_price.return_value = {
            'yes_ask': 0.75, 'no_ask': 0.25, 
            'yes_bid': 0.70, 'no_bid': 0.20
        }
        
        # No existing positions
        self.mock_risk_manager.get_positions_by_market.return_value = {}
        self.mock_risk_manager.can_open_position.return_value = True
        
        # Configure place_order to return the order dict it received
        self.mock_client.place_order.side_effect = lambda x: x
        
        trades = strategy.run()
        
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]['side'], 'BUY')
        self.assertEqual(trades[0]['outcome'], 'NO')
        self.assertEqual(trades[0]['price'], 0.25)
        print("✅ Entry Scan Verified: Bought NO at 0.25")

    def test_hedge_execution(self):
        """Test executing the second leg (hedge)"""
        strategy = LeggedArbitrageStrategy(
            name="legged",
            polymarket_client=self.mock_client,
            risk_manager=self.mock_risk_manager,
            config=self.config,
            market_cache=self.mock_market_cache
        )
        
        # Mock Existing Position: Long NO at 0.25
        pos = MockPosition('p1', 'm1', 'NO', 0.25, 100.0, 1234567890)
        self.mock_risk_manager.get_positions_by_market.return_value = {'m1': [pos]}
        
        # Mock Price Move: YES dropped to 0.45 (Total 0.25+0.45 = 0.70 < 0.95)
        self.mock_client.get_best_price.return_value = {
            'yes_ask': 0.45, 'no_ask': 0.55,
            'yes_bid': 0.40, 'no_bid': 0.50
        }
        
        # Configure place_order to return the order dict it received
        self.mock_client.place_order.side_effect = lambda x: x
        
        trades = strategy.run()
        
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]['side'], 'BUY')
        self.assertEqual(trades[0]['outcome'], 'YES') # Buying Opposite
        self.assertEqual(trades[0]['price'], 0.45)
        print("✅ Hedge Execution Verified: Bought YES at 0.45 (Arb Locked)")

if __name__ == '__main__':
    unittest.main()
