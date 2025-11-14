"""Tests for micro-spread strategy"""

import pytest
from unittest.mock import Mock, MagicMock
from src.strategies.micro_spreads import MicroSpreadStrategy
from src.api.polymarket_client import PolymarketClient
from src.risk.risk_manager import RiskManager


@pytest.fixture
def mock_polymarket_client():
    """Create mock Polymarket client"""
    client = Mock(spec=PolymarketClient)
    client.paper_trading = True
    
    # Mock get_markets
    client.get_markets.return_value = [
        {
            'id': 'market1',
            'question': 'Test market?'
        }
    ]
    
    # Mock get_best_price
    client.get_best_price.return_value = {
        'bid': 0.05,
        'ask': 0.06,
        'spread': 0.01
    }
    
    # Mock place_order
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


def test_micro_spread_strategy_initialization(mock_polymarket_client, mock_risk_manager):
    """Test micro-spread strategy initialization"""
    config = {
        'enabled': True,
        'min_buy_price': 0.05,
        'max_buy_price': 0.10,
        'position_size': 10.0
    }
    
    strategy = MicroSpreadStrategy(
        name='micro_spreads',
        polymarket_client=mock_polymarket_client,
        risk_manager=mock_risk_manager,
        config=config
    )
    
    assert strategy.name == 'micro_spreads'
    assert strategy.min_buy_price == 0.05
    assert strategy.position_size == 10.0


def test_scan_opportunities(mock_polymarket_client, mock_risk_manager):
    """Test opportunity scanning"""
    config = {
        'enabled': True,
        'min_buy_price': 0.05,
        'max_buy_price': 0.10,
        'min_profit_pct': 20.0
    }
    
    strategy = MicroSpreadStrategy(
        name='micro_spreads',
        polymarket_client=mock_polymarket_client,
        risk_manager=mock_risk_manager,
        config=config
    )
    
    opportunities = strategy.scan_opportunities()
    
    assert len(opportunities) > 0
    assert 'market_id' in opportunities[0]
    assert 'buy_price' in opportunities[0]
    assert 'sell_price' in opportunities[0]

