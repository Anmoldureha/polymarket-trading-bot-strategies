"""Tests for risk management system"""

import pytest
from src.risk.risk_manager import RiskManager
from src.risk.position_tracker import Position


def test_risk_manager_initialization():
    """Test risk manager initialization"""
    config = {
        'max_position_size': 1000.0,
        'max_total_exposure': 10000.0,
        'initial_capital': 10000.0
    }
    rm = RiskManager(config)
    assert rm.max_position_size == 1000.0
    assert rm.max_total_exposure == 10000.0


def test_trade_allowed():
    """Test trade approval logic"""
    config = {
        'max_position_size': 1000.0,
        'max_total_exposure': 10000.0,
        'max_per_market_exposure': 2000.0,
        'max_per_strategy_exposure': 5000.0,
        'max_open_positions': 50,
        'initial_capital': 10000.0
    }
    rm = RiskManager(config)
    
    # Small trade should be allowed
    allowed, reason = rm.check_trade_allowed(
        strategy='test',
        market_id='market1',
        size=100.0,
        price=0.5,
        side='buy'
    )
    assert allowed is True
    assert reason is None
    
    # Trade exceeding position size should be rejected
    allowed, reason = rm.check_trade_allowed(
        strategy='test',
        market_id='market1',
        size=2000.0,
        price=0.5,
        side='buy'
    )
    assert allowed is False
    assert 'exceeds max position size' in reason.lower()


def test_stop_loss():
    """Test stop loss checking"""
    config = {
        'stop_loss_pct': 10.0,
        'initial_capital': 10000.0
    }
    rm = RiskManager(config)
    
    # Add a position
    position = Position(
        position_id='test1',
        market_id='market1',
        strategy='test',
        side='buy',
        size=100.0,
        entry_price=0.5
    )
    rm.add_position(position)
    
    # Check stop loss with price down 15% (should trigger)
    triggered = rm.check_stop_loss('test1', 0.425)  # 15% down
    assert triggered is True
    
    # Check stop loss with price down 5% (should not trigger)
    position2 = Position(
        position_id='test2',
        market_id='market2',
        strategy='test',
        side='buy',
        size=100.0,
        entry_price=0.5
    )
    rm.add_position(position2)
    triggered = rm.check_stop_loss('test2', 0.475)  # 5% down
    assert triggered is False

