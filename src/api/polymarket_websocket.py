"""WebSocket client for real-time Polymarket data"""

import json
import time
import threading
import websocket
from typing import Dict, List, Optional, Callable
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


class PolymarketWebSocketClient:
    """WebSocket client for real-time Polymarket orderbook updates"""
    
    # Polymarket WebSocket endpoint from official documentation
    # https://docs.polymarket.com/developers/CLOB/endpoints
    # Error message indicates channels are '/ws/user' and '/ws/market'
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    
    def __init__(self, api_key: Optional[str] = None, private_key: Optional[str] = None):
        """
        Initialize WebSocket client.
        
        Args:
            api_key: Polymarket API key (optional, required for USER channel)
            private_key: Polymarket private key (optional, required for USER channel)
        """
        self.api_key = api_key
        self.private_key = private_key
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5.0
        
        # Subscriptions - track asset_ids for MARKET channel
        self.subscriptions: Dict[str, set] = {}  # market_id -> set of outcomes
        self.asset_id_map: Dict[str, tuple] = {}  # asset_id -> (market_id, outcome)
        self.orderbook_cache: Dict[str, Dict] = {}  # (market_id, outcome) -> orderbook
        self.pending_subscriptions: List[tuple] = []  # List of (market_id, outcome) to subscribe
        
        # Callbacks
        self.on_orderbook_update: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        
        # Threading
        self.lock = threading.Lock()
        self.ws_thread = None
        self.running = False
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages from Polymarket MARKET channel
        
        According to Polymarket docs: https://docs.polymarket.com/developers/CLOB/websocket/market-channel
        Messages have event_type: "book", "price_change", "tick_size_change", "last_trade_price"
        """
        try:
            data = json.loads(message)
            
            if not isinstance(data, dict):
                return
            
            # Handle different event types from MARKET channel
            event_type = data.get('event_type', '').lower()
            
            if event_type == 'book':
                # Book message - full orderbook snapshot
                self._handle_book_message(data)
            elif event_type == 'price_change':
                # Price change message - incremental updates
                self._handle_price_change_message(data)
            elif event_type == 'tick_size_change':
                # Tick size change - market tick size updated
                logger.debug(f"Tick size change: {data.get('market')}")
            elif event_type == 'last_trade_price':
                # Last trade - trade executed
                logger.debug(f"Last trade: {data.get('market')} @ {data.get('price')}")
            else:
                # Unknown message type - log for debugging
                logger.debug(f"Unknown WebSocket message type: {event_type}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    def _handle_book_message(self, data: Dict) -> None:
        """
        Handle 'book' event_type message from MARKET channel.
        
        Structure according to docs:
        - event_type: "book"
        - asset_id: token ID
        - market: condition ID
        - bids: OrderSummary[] with {price, size}
        - asks: OrderSummary[] with {price, size}
        """
        try:
            asset_id = data.get('asset_id')
            market_id = data.get('market')
            
            if not asset_id or not market_id:
                logger.debug(f"Book message missing asset_id or market: {data}")
                return
            
            # Convert Polymarket format to our format
            # Polymarket uses "bids"/"asks" with {price, size} objects
            bids_raw = data.get('bids', [])
            asks_raw = data.get('asks', [])
            
            # Convert to format expected by our code
            # Each bid/ask is {price: string, size: string}
            bids = [{'price': float(b.get('price', 0)), 'size': float(b.get('size', 0))} for b in bids_raw]
            asks = [{'price': float(a.get('price', 0)), 'size': float(a.get('size', 0))} for a in asks_raw]
            
            # Try to determine outcome from asset_id mapping or default to YES
            outcome = 'YES'  # Default
            if asset_id in self.asset_id_map:
                market_id, outcome = self.asset_id_map[asset_id]
            else:
                # Store mapping for future reference
                # Note: We'd need to fetch this from market data to know the outcome
                # For now, default to YES
                pass
            
            key = (market_id, outcome)
            
            with self.lock:
                self.orderbook_cache[key] = {
                    'bids': bids,
                    'asks': asks,
                    'timestamp': time.time()
                }
            
            # Call callback if set
            if self.on_orderbook_update:
                try:
                    self.on_orderbook_update(market_id, outcome, bids, asks)
                except Exception as e:
                    logger.error(f"Error in orderbook update callback: {e}")
        
        except Exception as e:
            logger.error(f"Error handling book message: {e}")
    
    def _handle_price_change_message(self, data: Dict) -> None:
        """
        Handle 'price_change' event_type message from MARKET channel.
        
        Structure according to docs:
        - event_type: "price_change"
        - market: condition ID
        - price_changes: PriceChange[] array
        """
        try:
            market_id = data.get('market')
            price_changes = data.get('price_changes', [])
            
            if not market_id or not price_changes:
                return
            
            # Price changes are incremental updates
            # We'd need to merge these into our cached orderbook
            # For now, log that we received them
            logger.debug(f"Price change received for market {market_id}: {len(price_changes)} changes")
            
            # TODO: Implement incremental orderbook update logic
            # For now, we rely on full 'book' messages for orderbook state
        
        except Exception as e:
            logger.error(f"Error handling price change message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
        self.connected = False
        
        if self.on_error:
            try:
                self.on_error(error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False
        
        # Attempt reconnection if running
        if self.running:
            self._reconnect()
    
    def _on_open(self, ws):
        """
        Handle WebSocket open - send initial subscription for MARKET channel.
        
        According to Polymarket docs, we subscribe to MARKET channel with:
        - type: "MARKET"
        - asset_ids: array of token IDs (can be empty initially)
        """
        logger.info("WebSocket connected")
        self.connected = True
        self.reconnect_attempts = 0
        
        # Send MARKET channel subscription
        # According to WSS overview: https://docs.polymarket.com/developers/CLOB/websocket/wss-overview
        # MARKET channel uses asset_ids array
        try:
            # Get asset_ids from pending subscriptions if any
            asset_ids = []
            # TODO: Resolve market_id/outcome to asset_ids from market data
            # For now, subscribe with empty array - we'll get book messages for subscribed assets
            
            subscribe_msg = {
                "type": "MARKET",
                "asset_ids": asset_ids
            }
            
            ws.send(json.dumps(subscribe_msg))
            logger.info("Subscribed to MARKET channel")
        except Exception as e:
            logger.error(f"Failed to send MARKET channel subscription: {e}")
        
        # Re-subscribe to all previous subscriptions
        self._resubscribe_all()
        
        if self.on_connect:
            try:
                self.on_connect()
            except Exception as e:
                logger.error(f"Error in connect callback: {e}")
    
    def _reconnect(self) -> None:
        """Attempt to reconnect WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            self.running = False
            return
        
        self.reconnect_attempts += 1
        wait_time = self.reconnect_delay * self.reconnect_attempts
        
        logger.info(f"Reconnecting in {wait_time:.1f}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        time.sleep(wait_time)
        
        try:
            self.connect()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            if self.running:
                self._reconnect()
    
    def _resubscribe_all(self) -> None:
        """Re-subscribe to all previous subscriptions"""
        with self.lock:
            for market_id, outcomes in self.subscriptions.items():
                for outcome in outcomes:
                    self._subscribe(market_id, outcome)
    
    def _subscribe(self, market_id: str, outcome: str = "YES") -> None:
        """
        Subscribe to orderbook updates for a market.
        Note: This requires asset_id (token ID) which we'll need to fetch from market data.
        For now, we'll queue the subscription and try to resolve asset_id later.
        """
        if not self.connected or not self.ws:
            # Queue for later
            self.pending_subscriptions.append((market_id, outcome))
            return
        
        try:
            # For MARKET channel, we need asset_ids (token IDs)
            # The asset_id is typically the token ID for the outcome
            # We'll need to get this from market data or use market_id as fallback
            # For now, use a simplified approach - try to construct asset_id
            # In production, you'd fetch the actual token ID from market data
            
            # Note: Polymarket MARKET channel uses asset_ids array
            # We need to send updated subscription with all asset_ids we want to track
            asset_ids = []
            
            # Try to get asset_id from cache or use market_id as identifier
            # In a full implementation, we'd fetch token IDs from market data
            # For now, we'll use market_id + outcome as a key and let the adapter handle it
            
            # Store subscription for later resolution
            key = (market_id, outcome)
            with self.lock:
                if market_id not in self.subscriptions:
                    self.subscriptions[market_id] = set()
                self.subscriptions[market_id].add(outcome)
            
            logger.debug(f"Queued subscription for {market_id} {outcome} (asset_id resolution needed)")
            
            # Note: Actual subscription will happen when we have asset_ids
            # For now, the REST fallback will handle data retrieval
        
        except Exception as e:
            logger.error(f"Failed to subscribe to {market_id} {outcome}: {e}")
    
    def connect(self) -> bool:
        """
        Connect to WebSocket.
        
        Returns:
            True if connected successfully
        """
        if self.connected:
            return True
        
        try:
            # Create WebSocket connection
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            self.ws = websocket.WebSocketApp(
                self.WS_URL,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open,
                header=headers
            )
            
            # Start WebSocket in a separate thread
            self.running = True
            self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            self.ws_thread.start()
            
            # Wait for connection
            timeout = 10.0
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            return self.connected
        
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            self.connected = False
            return False
    
    def subscribe_orderbook(self, market_id: str, outcome: str = "YES") -> None:
        """
        Subscribe to orderbook updates for a market.
        
        Args:
            market_id: Market identifier
            outcome: Outcome type (YES, NO, etc.)
        """
        key = (market_id, outcome)
        
        with self.lock:
            if market_id not in self.subscriptions:
                self.subscriptions[market_id] = set()
            self.subscriptions[market_id].add(outcome)
        
        if self.connected:
            self._subscribe(market_id, outcome)
        else:
            # Will subscribe on connect
            logger.debug(f"Queued subscription for {market_id} {outcome}")
    
    def unsubscribe_orderbook(self, market_id: str, outcome: str = "YES") -> None:
        """
        Unsubscribe from orderbook updates.
        
        Args:
            market_id: Market identifier
            outcome: Outcome type
        """
        with self.lock:
            if market_id in self.subscriptions:
                self.subscriptions[market_id].discard(outcome)
                if not self.subscriptions[market_id]:
                    del self.subscriptions[market_id]
            
            key = (market_id, outcome)
            if key in self.orderbook_cache:
                del self.orderbook_cache[key]
        
        if self.connected and self.ws:
            try:
                unsubscribe_msg = {
                    'type': 'unsubscribe',
                    'channel': 'orderbook',
                    'market': market_id,
                    'outcome': outcome
                }
                self.ws.send(json.dumps(unsubscribe_msg))
            except Exception as e:
                logger.error(f"Failed to unsubscribe: {e}")
    
    def get_orderbook(self, market_id: str, outcome: str = "YES") -> Optional[Dict]:
        """
        Get cached orderbook data.
        
        Args:
            market_id: Market identifier
            outcome: Outcome type
            
        Returns:
            Orderbook dict or None if not available
        """
        key = (market_id, outcome)
        
        with self.lock:
            return self.orderbook_cache.get(key)
    
    def disconnect(self) -> None:
        """Disconnect WebSocket"""
        self.running = False
        
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        
        self.connected = False
        logger.info("WebSocket disconnected")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.connected

