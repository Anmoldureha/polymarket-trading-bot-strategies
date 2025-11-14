"""Order coordination and lifecycle management"""

import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class Order:
    """Represents a trading order"""
    order_id: str
    market_id: str
    outcome: str
    side: str  # 'buy' or 'sell'
    size: float
    price: float
    filled_size: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    strategy: str = ""
    metadata: Dict = field(default_factory=dict)


class OrderCoordinator:
    """Manages order lifecycle and prevents duplicates"""
    
    def __init__(self):
        """Initialize order coordinator"""
        self.orders: Dict[str, Order] = {}
        self.pending_orders: Set[str] = set()
        self.filled_orders: List[Order] = []
        self.lock = None  # Will be set if threading is needed
    
    def create_order(
        self,
        order_id: str,
        market_id: str,
        outcome: str,
        side: str,
        size: float,
        price: float,
        strategy: str = "",
        metadata: Optional[Dict] = None
    ) -> Order:
        """
        Create and track a new order.
        
        Args:
            order_id: Unique order identifier
            market_id: Market identifier
            outcome: Outcome type
            side: 'buy' or 'sell'
            size: Order size
            price: Order price
            strategy: Strategy name
            metadata: Additional metadata
            
        Returns:
            Order object
        """
        # Check for duplicate orders
        if self._is_duplicate(market_id, outcome, side, price, size):
            raise ValueError(f"Duplicate order detected: {market_id} {outcome} {side} @ {price}")
        
        order = Order(
            order_id=order_id,
            market_id=market_id,
            outcome=outcome,
            side=side,
            size=size,
            price=price,
            strategy=strategy,
            metadata=metadata or {}
        )
        
        self.orders[order_id] = order
        self.pending_orders.add(order_id)
        
        logger.debug(f"Created order: {order_id} | {side} {size} @ {price} on {market_id}")
        
        return order
    
    def _is_duplicate(
        self,
        market_id: str,
        outcome: str,
        side: str,
        price: float,
        size: float,
        tolerance: float = 0.0001
    ) -> bool:
        """
        Check if a similar order already exists.
        
        Args:
            market_id: Market identifier
            outcome: Outcome type
            side: Order side
            price: Order price
            size: Order size
            tolerance: Price tolerance for duplicate detection
            
        Returns:
            True if duplicate found
        """
        for order_id in self.pending_orders:
            order = self.orders.get(order_id)
            if not order:
                continue
            
            if (order.market_id == market_id and
                order.outcome == outcome and
                order.side == side and
                abs(order.price - price) < tolerance and
                abs(order.size - size) < tolerance):
                return True
        
        return False
    
    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_size: Optional[float] = None
    ) -> Optional[Order]:
        """
        Update order status.
        
        Args:
            order_id: Order identifier
            status: New status
            filled_size: Filled size (if partially filled)
            
        Returns:
            Updated order or None if not found
        """
        order = self.orders.get(order_id)
        if not order:
            logger.warning(f"Order not found: {order_id}")
            return None
        
        order.status = status
        order.updated_at = datetime.now()
        
        if filled_size is not None:
            order.filled_size = filled_size
        
        # Move to appropriate collection
        if status == OrderStatus.FILLED:
            self.pending_orders.discard(order_id)
            if order not in self.filled_orders:
                self.filled_orders.append(order)
        elif status == OrderStatus.CANCELLED or status == OrderStatus.FAILED:
            self.pending_orders.discard(order_id)
        
        logger.debug(f"Updated order {order_id}: {status.value}")
        
        return order
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Mark order as cancelled.
        
        Args:
            order_id: Order identifier
            
        Returns:
            True if order was cancelled
        """
        order = self.update_order_status(order_id, OrderStatus.CANCELLED)
        return order is not None
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order by ID.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order or None
        """
        return self.orders.get(order_id)
    
    def get_pending_orders(
        self,
        market_id: Optional[str] = None,
        strategy: Optional[str] = None
    ) -> List[Order]:
        """
        Get pending orders.
        
        Args:
            market_id: Filter by market (optional)
            strategy: Filter by strategy (optional)
            
        Returns:
            List of pending orders
        """
        orders = []
        for order_id in self.pending_orders:
            order = self.orders.get(order_id)
            if not order:
                continue
            
            if market_id and order.market_id != market_id:
                continue
            
            if strategy and order.strategy != strategy:
                continue
            
            orders.append(order)
        
        return orders
    
    def get_orders_by_market(self, market_id: str) -> List[Order]:
        """
        Get all orders for a market.
        
        Args:
            market_id: Market identifier
            
        Returns:
            List of orders
        """
        return [order for order in self.orders.values() if order.market_id == market_id]
    
    def reconcile_orders(self, exchange_orders: List[Dict]) -> Dict:
        """
        Reconcile internal order state with exchange state.
        
        Args:
            exchange_orders: List of orders from exchange API
            
        Returns:
            Reconciliation report
        """
        exchange_order_ids = {order.get('order_id') for order in exchange_orders if order.get('order_id')}
        
        report = {
            'matched': 0,
            'missing_on_exchange': [],
            'missing_locally': [],
            'status_mismatches': []
        }
        
        # Check our pending orders against exchange
        for order_id in list(self.pending_orders):
            order = self.orders.get(order_id)
            if not order:
                continue
            
            # Find matching exchange order
            exchange_order = next(
                (eo for eo in exchange_orders if eo.get('order_id') == order_id),
                None
            )
            
            if not exchange_order:
                # Order not found on exchange - might be filled or cancelled
                report['missing_on_exchange'].append(order_id)
                # Could mark as filled if it's been a while
                time_since_creation = (datetime.now() - order.created_at).total_seconds()
                if time_since_creation > 300:  # 5 minutes
                    logger.warning(f"Order {order_id} missing on exchange for {time_since_creation}s, marking as filled")
                    self.update_order_status(order_id, OrderStatus.FILLED)
            else:
                report['matched'] += 1
                # Check status mismatch
                exchange_status = exchange_order.get('status', '').lower()
                if exchange_status == 'filled' and order.status != OrderStatus.FILLED:
                    self.update_order_status(order_id, OrderStatus.FILLED)
                    report['status_mismatches'].append(order_id)
                elif exchange_status == 'cancelled' and order.status != OrderStatus.CANCELLED:
                    self.update_order_status(order_id, OrderStatus.CANCELLED)
                    report['status_mismatches'].append(order_id)
        
        # Check for orders on exchange that we don't know about
        for exchange_order in exchange_orders:
            order_id = exchange_order.get('order_id')
            if order_id and order_id not in self.orders:
                report['missing_locally'].append(order_id)
        
        return report
    
    def get_stats(self) -> Dict:
        """
        Get order coordinator statistics.
        
        Returns:
            Statistics dictionary
        """
        total_orders = len(self.orders)
        pending_count = len(self.pending_orders)
        filled_count = len(self.filled_orders)
        
        return {
            'total_orders': total_orders,
            'pending_orders': pending_count,
            'filled_orders': filled_count,
            'cancelled_orders': total_orders - pending_count - filled_count
        }

