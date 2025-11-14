"""Risk management engine"""

from typing import Dict, Optional, Tuple
from decimal import Decimal
from ..utils.logger import setup_logger
from ..risk.position_tracker import PositionTracker, Position


logger = setup_logger(__name__)


class RiskManager:
    """Centralized risk management for all trading operations"""
    
    def __init__(self, config: Dict):
        """
        Initialize risk manager.
        
        Args:
            config: Risk configuration dictionary
        """
        self.config = config
        self.position_tracker = PositionTracker()
        
        # Risk limits with defaults
        self.max_position_size = config.get('max_position_size', 1000.0)
        self.max_total_exposure = config.get('max_total_exposure', 10000.0)
        self.max_per_market_exposure = config.get('max_per_market_exposure', 2000.0)
        self.max_per_strategy_exposure = config.get('max_per_strategy_exposure', 5000.0)
        self.max_drawdown_pct = config.get('max_drawdown_pct', 20.0)
        self.max_open_positions = config.get('max_open_positions', 50)
        self.stop_loss_pct = config.get('stop_loss_pct', 10.0)
        
        # Track initial capital for drawdown calculation
        self.initial_capital = config.get('initial_capital', 10000.0)
        self.peak_capital = self.initial_capital
    
    def check_trade_allowed(
        self,
        strategy: str,
        market_id: str,
        size: float,
        price: float,
        side: str = 'buy'
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a trade is allowed based on risk limits.
        
        Args:
            strategy: Strategy name
            market_id: Market identifier
            size: Trade size
            price: Trade price
            side: 'buy' or 'sell'
            
        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
        """
        trade_value = size * price
        
        # Check position size limit
        if trade_value > self.max_position_size:
            return False, f"Trade size ${trade_value:.2f} exceeds max position size ${self.max_position_size:.2f}"
        
        # Check total exposure
        current_exposure = self.position_tracker.get_total_exposure()
        if current_exposure + trade_value > self.max_total_exposure:
            return False, f"Total exposure ${current_exposure + trade_value:.2f} exceeds limit ${self.max_total_exposure:.2f}"
        
        # Check per-market exposure
        market_positions = self.position_tracker.get_positions_by_market(market_id)
        market_exposure = sum(p.entry_price * p.size for p in market_positions)
        if market_exposure + trade_value > self.max_per_market_exposure:
            return False, f"Market exposure ${market_exposure + trade_value:.2f} exceeds limit ${self.max_per_market_exposure:.2f}"
        
        # Check per-strategy exposure
        strategy_positions = self.position_tracker.get_positions_by_strategy(strategy)
        strategy_exposure = sum(p.entry_price * p.size for p in strategy_positions)
        if strategy_exposure + trade_value > self.max_per_strategy_exposure:
            return False, f"Strategy exposure ${strategy_exposure + trade_value:.2f} exceeds limit ${self.max_per_strategy_exposure:.2f}"
        
        # Check open position count
        if self.position_tracker.get_open_position_count() >= self.max_open_positions:
            return False, f"Open positions {self.position_tracker.get_open_position_count()} exceeds limit {self.max_open_positions}"
        
        # Check drawdown
        current_capital = self.initial_capital + self.position_tracker.get_total_pnl()
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital
        
        drawdown_pct = ((self.peak_capital - current_capital) / self.peak_capital) * 100
        if drawdown_pct > self.max_drawdown_pct:
            return False, f"Drawdown {drawdown_pct:.2f}% exceeds limit {self.max_drawdown_pct:.2f}%"
        
        return True, None
    
    def add_position(self, position: Position) -> None:
        """
        Add a position to tracking.
        
        Args:
            position: Position to add
        """
        self.position_tracker.add_position(position)
    
    def check_stop_loss(self, position_id: str, current_price: float) -> bool:
        """
        Check if a position should be stopped out.
        
        Args:
            position_id: Position identifier
            current_price: Current market price
            
        Returns:
            True if stop loss triggered
        """
        if position_id not in self.position_tracker.positions:
            return False
        
        position = self.position_tracker.positions[position_id]
        
        # Calculate current P&L percentage
        if position.side == 'buy':
            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        else:  # sell
            pnl_pct = ((position.entry_price - current_price) / position.entry_price) * 100
        
        if pnl_pct <= -self.stop_loss_pct:
            logger.warning(f"Stop loss triggered for {position_id}: {pnl_pct:.2f}%")
            return True
        
        return False
    
    def get_risk_metrics(self) -> Dict:
        """
        Get current risk metrics.
        
        Returns:
            Dictionary of risk metrics
        """
        total_exposure = self.position_tracker.get_total_exposure()
        total_pnl = self.position_tracker.get_total_pnl()
        current_capital = self.initial_capital + total_pnl
        
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital
        
        drawdown_pct = ((self.peak_capital - current_capital) / self.peak_capital) * 100 if self.peak_capital > 0 else 0
        
        return {
            'total_exposure': total_exposure,
            'total_pnl': total_pnl,
            'current_capital': current_capital,
            'peak_capital': self.peak_capital,
            'drawdown_pct': drawdown_pct,
            'open_positions': self.position_tracker.get_open_position_count(),
            'exposure_utilization': (total_exposure / self.max_total_exposure) * 100
        }
    
    def close_position(self, position_id: str, exit_price: float) -> Optional[Position]:
        """
        Close a position.
        
        Args:
            position_id: Position identifier
            exit_price: Exit price
            
        Returns:
            Closed position
        """
        return self.position_tracker.close_position(position_id, exit_price)

