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
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/"
    
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
        """Handle incoming WebSocket messages from Polymarket MARKET channel"""
        try:
            data = json.loads(message)
            
            # Handle Polymarket MARKET channel messages
            # Messages can be orderbook updates, trades, or other market data
            if isinstance(data, dict):
                # Check for orderbook data structure
                if 'bids' in data and 'asks' in data:
                    # This is an orderbook update
                    self._handle_orderbook_update(data)
                elif 'type' in data:
                    msg_type = data.get('type')
                    if msg_type == 'error':
                        logger.error(f"WebSocket error: {data.get('message', 'Unknown error')}")
                        if self.on_error:
                            self.on_error(data)
                    elif msg_type == 'subscribed' or msg_type == 'SUBSCRIBED':
                        logger.debug(f"Subscription confirmed: {data.get('channel', 'unknown')}")
                    elif msg_type == 'orderbook' or msg_type == 'ORDERBOOK':
                        self._handle_orderbook_update(data)
                    elif msg_type == 'trade' or msg_type == 'TRADE':
                        # Handle trade updates if needed
                        logger.debug(f"Trade update received")
                else:
                    # Try to handle as orderbook update
                    if 'bids' in data or 'asks' in data:
                        self._handle_orderbook_update(data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    def _handle_orderbook_update(self, data: Dict) -> None:
        """Handle orderbook update message from MARKET channel"""
        try:
            # Polymarket MARKET channel messages may include asset_id or token_id
            asset_id = data.get('asset_id') or data.get('token_id') or data.get('tokenId')
            market_id = data.get('market') or data.get('market_id')
            outcome = data.get('outcome', 'YES')
            
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            # Try to map asset_id back to market_id/outcome if we have it
            if asset_id and asset_id in self.asset_id_map:
                market_id, outcome = self.asset_id_map[asset_id]
            
            # If we still don't have market_id, try to find it from subscriptions
            if not market_id:
                # For now, use a generic key - in production, we'd maintain proper mapping
                logger.debug(f"Orderbook update received but market_id not found, using asset_id: {asset_id}")
                return
            
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
            logger.error(f"Error handling orderbook update: {e}")
    
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
        """Handle WebSocket open - send initial subscription for MARKET channel"""
        logger.info("WebSocket connected")
        self.connected = True
        self.reconnect_attempts = 0
        
        # Send MARKET channel subscription
        # For MARKET channel, we need asset_ids (token IDs)
        # For now, subscribe with empty array - will add asset_ids as we subscribe to markets
        try:
            subscribe_msg = {
                "type": "MARKET",
                "asset_ids": []
            }
            
            # Add auth if available (for USER channel, not needed for MARKET)
            # MARKET channel doesn't require auth, but we can include it if available
            if self.api_key:
                # Note: Auth format may need adjustment based on Polymarket docs
                # For MARKET channel, auth is typically not required
                pass
            
            ws.send(json.dumps(subscribe_msg))
            logger.debug("Subscribed to MARKET channel")
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

