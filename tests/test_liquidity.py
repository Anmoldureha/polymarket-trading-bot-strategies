"""Tests for liquidity strategy"""

import pytest
from unittest.mock import Mock
from src.strategies.liquidity import LiquidityStrategy
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
            'question': 'Test market?'
        }
    ]
    
    # Wide spread: bid=0.45, ask=0.55 (10% spread)
    client.get_best_price.return_value = {
        'bid': 0.45,
        'ask': 0.55,
        'spread': 0.10
    }
    
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


def test_liquidity_strategy_scan(mock_polymarket_client, mock_risk_manager):
    """Test liquidity opportunity scanning"""
    config = {
        'enabled': True,
        'min_spread_pct': 2.0,
        'max_spread_pct': 10.0,
        'position_size': 50.0
    }
    
    strategy = LiquidityStrategy(
        name='liquidity',
        polymarket_client=mock_polymarket_client,
        risk_manager=mock_risk_manager,
        config=config
    )
    
    opportunities = strategy.scan_opportunities()
    
    assert len(opportunities) > 0
    opp = opportunities[0]
    assert 'current_spread_pct' in opp
    assert opp['current_spread_pct'] >= 2.0

