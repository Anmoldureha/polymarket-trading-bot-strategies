"""State persistence and recovery"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
from ..utils.logger import setup_logger
from ..risk.position_tracker import PositionTracker, Position
from ..core.order_coordinator import OrderCoordinator, Order, OrderStatus


logger = setup_logger(__name__)


class StateManager:
    """Manages bot state persistence and recovery"""
    
    def __init__(self, state_file: str = "bot_state.json"):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to state file
        """
        self.state_file = Path(state_file)
        self.state_dir = self.state_file.parent
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def save_state(
        self,
        position_tracker: PositionTracker,
        order_coordinator: OrderCoordinator,
        profitability_tracker: Any,
        additional_state: Optional[Dict] = None
    ) -> bool:
        """
        Save bot state to file.
        
        Args:
            position_tracker: Position tracker instance
            order_coordinator: Order coordinator instance
            profitability_tracker: Profitability tracker instance
            additional_state: Additional state to save
            
        Returns:
            True if saved successfully
        """
        try:
            state = {
                'timestamp': datetime.now().isoformat(),
                'positions': self._serialize_positions(position_tracker),
                'orders': self._serialize_orders(order_coordinator),
                'profitability': self._serialize_profitability(profitability_tracker),
                'additional': additional_state or {}
            }
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            # Atomic rename
            temp_file.replace(self.state_file)
            
            logger.info(f"State saved to {self.state_file}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False
    
    def _serialize_positions(self, tracker: PositionTracker) -> Dict:
        """Serialize positions to dict"""
        positions = []
        for position in tracker.positions.values():
            positions.append({
                'position_id': position.position_id,
                'market_id': position.market_id,
                'strategy': position.strategy,
                'side': position.side,
                'size': position.size,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'timestamp': position.timestamp.isoformat(),
                'status': position.status,
                'pnl': position.pnl,
                'pnl_pct': position.pnl_pct,
                'metadata': position.metadata
            })
        
        return {
            'open_positions': positions,
            'closed_positions_count': len(tracker.closed_positions)
        }
    
    def _serialize_orders(self, coordinator: OrderCoordinator) -> Dict:
        """Serialize orders to dict"""
        orders = []
        for order in coordinator.orders.values():
            orders.append({
                'order_id': order.order_id,
                'market_id': order.market_id,
                'outcome': order.outcome,
                'side': order.side,
                'size': order.size,
                'price': order.price,
                'filled_size': order.filled_size,
                'status': order.status.value,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat(),
                'strategy': order.strategy,
                'metadata': order.metadata
            })
        
        return {
            'all_orders': orders,
            'pending_order_ids': list(coordinator.pending_orders)
        }
    
    def _serialize_profitability(self, tracker: Any) -> Dict:
        """Serialize profitability tracker to dict"""
        try:
            stats = tracker.get_overall_stats()
            return {
                'initial_capital': tracker.initial_capital,
                'current_capital': tracker.current_capital,
                'total_trades': stats.get('total_trades', 0),
                'total_pnl': stats.get('total_pnl', 0.0),
                'roi': stats.get('roi', 0.0)
            }
        except Exception as e:
            logger.debug(f"Error serializing profitability: {e}")
            return {}
    
    def load_state(self) -> Optional[Dict]:
        """
        Load bot state from file.
        
        Returns:
            State dictionary or None if not found/invalid
        """
        if not self.state_file.exists():
            logger.debug(f"State file not found: {self.state_file}")
            return None
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            logger.info(f"State loaded from {self.state_file}")
            return state
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in state file: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return None
    
    def restore_positions(
        self,
        state: Dict,
        position_tracker: PositionTracker
    ) -> int:
        """
        Restore positions from state.
        
        Args:
            state: State dictionary
            position_tracker: Position tracker instance
            
        Returns:
            Number of positions restored
        """
        try:
            positions_data = state.get('positions', {}).get('open_positions', [])
            restored = 0
            
            for pos_data in positions_data:
                try:
                    position = Position(
                        position_id=pos_data['position_id'],
                        market_id=pos_data['market_id'],
                        strategy=pos_data['strategy'],
                        side=pos_data['side'],
                        size=pos_data['size'],
                        entry_price=pos_data['entry_price'],
                        current_price=pos_data.get('current_price'),
                        timestamp=datetime.fromisoformat(pos_data['timestamp']),
                        status=pos_data['status'],
                        pnl=pos_data.get('pnl', 0.0),
                        pnl_pct=pos_data.get('pnl_pct', 0.0),
                        metadata=pos_data.get('metadata', {})
                    )
                    
                    position_tracker.add_position(position)
                    restored += 1
                
                except Exception as e:
                    logger.warning(f"Failed to restore position {pos_data.get('position_id')}: {e}")
            
            if restored > 0:
                logger.info(f"Restored {restored} positions from state")
            
            return restored
        
        except Exception as e:
            logger.error(f"Error restoring positions: {e}")
            return 0
    
    def restore_orders(
        self,
        state: Dict,
        order_coordinator: OrderCoordinator
    ) -> int:
        """
        Restore orders from state.
        
        Args:
            state: State dictionary
            order_coordinator: Order coordinator instance
            
        Returns:
            Number of orders restored
        """
        try:
            orders_data = state.get('orders', {}).get('all_orders', [])
            restored = 0
            
            for order_data in orders_data:
                try:
                    # Only restore pending orders (filled/cancelled are historical)
                    status = OrderStatus(order_data['status'])
                    if status not in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]:
                        continue
                    
                    order = Order(
                        order_id=order_data['order_id'],
                        market_id=order_data['market_id'],
                        outcome=order_data['outcome'],
                        side=order_data['side'],
                        size=order_data['size'],
                        price=order_data['price'],
                        filled_size=order_data.get('filled_size', 0.0),
                        status=status,
                        created_at=datetime.fromisoformat(order_data['created_at']),
                        updated_at=datetime.fromisoformat(order_data['updated_at']),
                        strategy=order_data.get('strategy', ''),
                        metadata=order_data.get('metadata', {})
                    )
                    
                    order_coordinator.orders[order.order_id] = order
                    if status == OrderStatus.PENDING:
                        order_coordinator.pending_orders.add(order.order_id)
                    
                    restored += 1
                
                except Exception as e:
                    logger.warning(f"Failed to restore order {order_data.get('order_id')}: {e}")
            
            if restored > 0:
                logger.info(f"Restored {restored} orders from state")
            
            return restored
        
        except Exception as e:
            logger.error(f"Error restoring orders: {e}")
            return 0
    
    def clear_state(self) -> bool:
        """
        Clear saved state.
        
        Returns:
            True if cleared successfully
        """
        try:
            if self.state_file.exists():
                self.state_file.unlink()
                logger.info("State file cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear state: {e}")
            return False

