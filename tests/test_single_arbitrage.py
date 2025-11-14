"""Tests for single-market arbitrage strategy"""

import pytest
from unittest.mock import Mock
from src.strategies.single_arbitrage import SingleArbitrageStrategy
from src.api.polymarket_client import PolymarketClient
from src.risk.risk_manager import RiskManager


@pytest.fixture
def mock_polymarket_client():
    """Create mock Polymarket client"""
    client = Mock(spec=PolymarketClient)
    client.paper_trading = True
    
    client.get_markets.return_value = [
        {
            'id': 'market1',
            'question': 'Test market?',
            'resolution_source': 'official'
        }
    ]
    
    # Mock arbitrage opportunity: YES=0.45, NO=0.50 (total=0.95)
    client.get_best_price.side_effect = [
        {'ask': 0.45},  # YES
        {'ask': 0.50}   # NO
    ]
    
    client.place_order.return_value = {
        'order_id': 'order123',
        'status': 'pending'
    }
    
    return client


@pytest.fixture
def mock_risk_manager():
    """Create mock risk manager"""
    rm = Mock(spec=RiskManager)
    rm.check_trade_allowed.return_value = (True, None)
    rm.position_tracker = Mock()
    rm.position_tracker.positions = {}
    return rm


def test_single_arbitrage_scan(mock_polymarket_client, mock_risk_manager):
    """Test arbitrage opportunity scanning"""
    config = {
        'enabled': True,
        'max_total_price': 0.99,
        'min_profit_pct': 1.0,
        'position_size': 100.0
    }
    
    strategy = SingleArbitrageStrategy(
        name='single_arbitrage',
        polymarket_client=mock_polymarket_client,
        risk_manager=mock_risk_manager,
        config=config
    )
    
    opportunities = strategy.scan_opportunities()
    
    # Should find the arbitrage opportunity
    assert len(opportunities) > 0
    opp = opportunities[0]
    assert opp['total_price'] < 1.0
    assert opp['profit_pct'] > 0

