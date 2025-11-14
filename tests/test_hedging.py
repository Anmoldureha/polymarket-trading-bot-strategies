"""Tests for hedging strategy"""

import pytest
from unittest.mock import Mock
from src.strategies.hedging import HedgingStrategy
from src.api.polymarket_client import PolymarketClient
from src.api.perpdex_client import PerpdexClient
from src.risk.risk_manager import RiskManager


@pytest.fixture
def mock_polymarket_client():
    """Create mock Polymarket client"""
    client = Mock(spec=PolymarketClient)
    client.paper_trading = True
    
    client.get_markets.return_value = [
        {
            'id': 'market1',
            'question': 'Will Bitcoin reach $50k?'
        }
    ]
    
    client.get_best_price.return_value = {
        'ask': 0.4,  # Short opportunity
        'bid': 0.35
    }
    
    client.place_order.return_value = {
        'order_id': 'order123',
        'status': 'pending'
    }
    
    return client


@pytest.fixture
def mock_perpdex_client():
    """Create mock Perpdex client"""
    client = Mock(spec=PerpdexClient)
    client.paper_trading = True
    client.get_price.return_value = 45000.0
    
    client.open_position.return_value = {
        'position_id': 'perp123',
        'status': 'open'
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


def test_hedging_strategy_initialization(mock_polymarket_client, mock_perpdex_client, mock_risk_manager):
    """Test hedging strategy initialization"""
    config = {
        'enabled': True,
        'position_size': 100.0,
        'btc_market_keywords': ['bitcoin', 'btc']
    }
    
    strategy = HedgingStrategy(
        name='hedging',
        polymarket_client=mock_polymarket_client,
        risk_manager=mock_risk_manager,
        config=config,
        perpdex_client=mock_perpdex_client
    )
    
    assert strategy.name == 'hedging'
    assert strategy.perpdex_client is not None

