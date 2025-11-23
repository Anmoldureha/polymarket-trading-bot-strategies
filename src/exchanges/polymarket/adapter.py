"""Unified Polymarket exchange adapter"""

from typing import Dict, List, Optional
from ...exchanges.base_exchange import BaseExchange
from .rest_client import PolymarketRESTClient
from ...api.polymarket_websocket import PolymarketWebSocketClient
from ...utils.logger import setup_logger


logger = setup_logger(__name__)


class PolymarketAdapter(BaseExchange):
    """Unified adapter for Polymarket exchange"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        private_key: Optional[str] = None,
        paper_trading: bool = False,
        use_websocket: bool = False
    ):
        """
        Initialize Polymarket adapter.
        
        Args:
            api_key: API key
            private_key: Private key
            paper_trading: Paper trading mode
            use_websocket: Enable WebSocket for real-time data
        """
        # REST client (always available)
        self.rest_client = PolymarketRESTClient(
            api_key=api_key,
            private_key=private_key,
            paper_trading=paper_trading
        )
        
        # WebSocket client (optional)
        self.ws_client: Optional[PolymarketWebSocketClient] = None
        self.use_websocket = False
        
        if use_websocket:
            self._enable_websocket()
        
        # Order coordinator reference (set by bot)
        self._order_coordinator = None
    
    def _enable_websocket(self) -> bool:
        """Enable WebSocket client"""
        if self.ws_client and self.ws_client.is_connected():
            return True
        
        try:
            self.ws_client = PolymarketWebSocketClient(
                api_key=self.rest_client.api_key,
                private_key=getattr(self.rest_client, 'private_key', None)
            )
            # Provide rest_client reference for fetching asset_ids
            self.ws_client.rest_client = self.rest_client
            
            def on_orderbook_update(market_id, outcome, bids, asks):
                logger.debug(f"Orderbook update: {market_id} {outcome}")
            
            self.ws_client.on_orderbook_update = on_orderbook_update
            
            if self.ws_client.connect():
                self.use_websocket = True
                logger.info("✅ WebSocket enabled for real-time data")
                return True
            else:
                logger.warning("⚠️  Failed to connect WebSocket, using REST only (this is OK for paper trading)")
                logger.info("   WebSocket will be used automatically when connection is available")
                # Don't fail - REST fallback is fine
                return False
        except Exception as e:
            logger.error(f"Error enabling WebSocket: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if exchange is connected"""
        # REST is always available, WebSocket is optional
        if self.use_websocket:
            return self.ws_client is not None and self.ws_client.is_connected()
        return True
    
    def get_markets(self, active: bool = True, limit: int = 100) -> List[Dict]:
        """Get markets - always uses REST
        
        Args:
            active: Filter for active markets
            limit: Max number of markets to return (uses pagination if > 1000)
        """
        if limit <= 1000:
            # Single page request
            result = self.rest_client.get_markets(active=active, limit=limit)
            return result['markets']
        else:
            # Multi-page request
            return self.rest_client.get_all_markets(active=active, max_markets=limit)
    
    def get_market(self, market_id: str) -> Dict:
        """Get market details - always uses REST"""
        endpoint = f"/markets/{market_id}"
        return self.rest_client._request('GET', endpoint)
    
    def get_orderbook(self, market_id: str, outcome: str = "YES") -> Dict:
        """Get orderbook - tries WebSocket first, falls back to REST"""
        # Try WebSocket if enabled
        if self.use_websocket and self.ws_client and self.ws_client.is_connected():
            cached = self.ws_client.get_orderbook(market_id, outcome)
            if cached:
                return cached
            
            # Subscribe and wait (pass rest_client to get asset_ids)
            self.ws_client.subscribe_orderbook(market_id, outcome, rest_client=self.rest_client)
            import time
            time.sleep(0.5)
            cached = self.ws_client.get_orderbook(market_id, outcome)
            if cached:
                return cached
        
        # Fallback to REST
        return self.rest_client.get_orderbook(market_id, outcome)
    
    def get_best_price(self, market_id: str, outcome: str = "YES") -> Dict:
        """Get best prices"""
        orderbook = self.get_orderbook(market_id, outcome)
        
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        best_bid = float(bids[0]['price']) if bids and isinstance(bids[0], dict) else None
        best_ask = float(asks[0]['price']) if asks and isinstance(asks[0], dict) else None
        
        prices = {
            'bid': best_bid,
            'ask': best_ask,
            'spread': best_ask - best_bid if (best_bid and best_ask) else None
        }
        
        # Validate
        is_valid, error_msg = self.rest_client.validator.validate_price_response(prices)
        if not is_valid:
            logger.warning(f"Invalid prices: {error_msg}")
        
        return prices
    
    def place_order(
        self,
        market_id: str,
        outcome: str,
        side: str,
        size: float,
        price: float,
        order_coordinator=None,
        strategy: str = ""
    ) -> Dict:
        """Place order"""
        result = self.rest_client.place_order(market_id, outcome, side, size, price)
        
        # Register with order coordinator if provided
        if order_coordinator and 'order_id' in result:
            try:
                order_coordinator.create_order(
                    order_id=result['order_id'],
                    market_id=market_id,
                    outcome=outcome,
                    side=side,
                    size=size,
                    price=price,
                    strategy=strategy
                )
            except ValueError as e:
                logger.warning(f"Order coordinator rejected order: {e}")
        
        return result
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel order"""
        return self.rest_client.cancel_order(order_id)
    
    def get_orders(self, market_id: Optional[str] = None, status: str = "open") -> List[Dict]:
        """Get orders"""
        return self.rest_client.get_orders(market_id=market_id, status=status)
    
    def get_positions(self, market_id: Optional[str] = None) -> List[Dict]:
        """Get positions"""
        return self.rest_client.get_positions(market_id=market_id)
    
    def get_balance(self) -> Dict:
        """Get balance"""
        return self.rest_client.get_balance()

