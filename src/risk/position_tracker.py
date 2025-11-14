"""Position tracking system"""

from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


@dataclass
class Position:
    """Represents a trading position"""
    position_id: str
    market_id: str
    strategy: str
    side: str  # 'buy' or 'sell'
    size: float
    entry_price: float
    current_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = 'open'  # 'open', 'closed', 'partial'
    pnl: float = 0.0
    pnl_pct: float = 0.0
    metadata: Dict = field(default_factory=dict)


class PositionTracker:
    """Track all open and closed positions"""
    
    def __init__(self):
        """Initialize position tracker"""
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
    
    def add_position(self, position: Position) -> None:
        """
        Add a new position.
        
        Args:
            position: Position to add
        """
        self.positions[position.position_id] = position
        logger.debug(f"Added position: {position.position_id} ({position.strategy})")
    
    def update_position(self, position_id: str, **kwargs) -> None:
        """
        Update position fields.
        
        Args:
            position_id: Position identifier
            **kwargs: Fields to update
        """
        if position_id not in self.positions:
            logger.warning(f"Position not found: {position_id}")
            return
        
        position = self.positions[position_id]
        for key, value in kwargs.items():
            if hasattr(position, key):
                setattr(position, key, value)
    
    def close_position(self, position_id: str, exit_price: float) -> Optional[Position]:
        """
        Close a position.
        
        Args:
            position_id: Position identifier
            exit_price: Exit price
            
        Returns:
            Closed position or None if not found
        """
        if position_id not in self.positions:
            logger.warning(f"Position not found for closing: {position_id}")
            return None
        
        position = self.positions[position_id]
        position.current_price = exit_price
        position.status = 'closed'
        
        # Calculate P&L
        if position.side == 'buy':
            position.pnl = (exit_price - position.entry_price) * position.size
        else:  # sell
            position.pnl = (position.entry_price - exit_price) * position.size
        
        position.pnl_pct = (position.pnl / (position.entry_price * position.size)) * 100
        
        # Move to closed positions
        self.closed_positions.append(position)
        del self.positions[position_id]
        
        logger.info(f"Closed position: {position_id} | P&L: ${position.pnl:.2f} ({position.pnl_pct:.2f}%)")
        return position
    
    def get_positions_by_strategy(self, strategy: str) -> List[Position]:
        """
        Get all open positions for a strategy.
        
        Args:
            strategy: Strategy name
            
        Returns:
            List of positions
        """
        return [p for p in self.positions.values() if p.strategy == strategy]
    
    def get_positions_by_market(self, market_id: str) -> List[Position]:
        """
        Get all open positions for a market.
        
        Args:
            market_id: Market identifier
            
        Returns:
            List of positions
        """
        return [p for p in self.positions.values() if p.market_id == market_id]
    
    def get_total_exposure(self, strategy: Optional[str] = None) -> float:
        """
        Calculate total exposure across positions.
        
        Args:
            strategy: Filter by strategy (optional)
            
        Returns:
            Total exposure in USD
        """
        positions = self.positions.values()
        if strategy:
            positions = [p for p in positions if p.strategy == strategy]
        
        return sum(p.entry_price * p.size for p in positions)
    
    def get_total_pnl(self) -> float:
        """
        Calculate total P&L from closed positions.
        
        Returns:
            Total P&L
        """
        return sum(p.pnl for p in self.closed_positions)
    
    def get_open_position_count(self) -> int:
        """Get count of open positions"""
        return len(self.positions)

