"""Base exchange interface"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseExchange(ABC):
    """Base interface for all exchange adapters"""
    
    @abstractmethod
    def get_markets(self, active: bool = True, limit: int = 100) -> List[Dict]:
        """Get list of markets"""
        pass
    
    @abstractmethod
    def get_market(self, market_id: str) -> Dict:
        """Get market details"""
        pass
    
    @abstractmethod
    def get_orderbook(self, market_id: str, outcome: str = "YES") -> Dict:
        """Get orderbook"""
        pass
    
    @abstractmethod
    def get_best_price(self, market_id: str, outcome: str = "YES") -> Dict:
        """Get best bid/ask prices"""
        pass
    
    @abstractmethod
    def place_order(
        self,
        market_id: str,
        outcome: str,
        side: str,
        size: float,
        price: float
    ) -> Dict:
        """Place a limit order"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def get_orders(self, market_id: Optional[str] = None, status: str = "open") -> List[Dict]:
        """Get user's orders"""
        pass
    
    @abstractmethod
    def get_positions(self, market_id: Optional[str] = None) -> List[Dict]:
        """Get user's positions"""
        pass
    
    @abstractmethod
    def get_balance(self) -> Dict:
        """Get account balance"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if exchange is connected"""
        pass

