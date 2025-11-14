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
    
    WS_URL = "wss://clob.polymarket.com/ws"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize WebSocket client.
        
        Args:
            api_key: Polymarket API key (optional)
        """
        self.api_key = api_key
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5.0
        
        # Subscriptions
        self.subscriptions: Dict[str, set] = {}  # market_id -> set of outcomes
        self.orderbook_cache: Dict[str, Dict] = {}  # (market_id, outcome) -> orderbook
        
        # Callbacks
        self.on_orderbook_update: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        
        # Threading
        self.lock = threading.Lock()
        self.ws_thread = None
        self.running = False
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Handle different message types
            if 'type' in data:
                if data['type'] == 'orderbook':
                    self._handle_orderbook_update(data)
                elif data['type'] == 'error':
                    logger.error(f"WebSocket error: {data.get('message', 'Unknown error')}")
                    if self.on_error:
                        self.on_error(data)
                elif data['type'] == 'subscribed':
                    logger.debug(f"Subscribed to: {data.get('channel', 'unknown')}")
                elif data['type'] == 'pong':
                    # Heartbeat response
                    pass
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    def _handle_orderbook_update(self, data: Dict) -> None:
        """Handle orderbook update message"""
        try:
            market_id = data.get('market')
            outcome = data.get('outcome', 'YES')
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            if not market_id:
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
        """Handle WebSocket open"""
        logger.info("WebSocket connected")
        self.connected = True
        self.reconnect_attempts = 0
        
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
        """Subscribe to orderbook updates for a market"""
        if not self.connected or not self.ws:
            return
        
        try:
            subscribe_msg = {
                'type': 'subscribe',
                'channel': 'orderbook',
                'market': market_id,
                'outcome': outcome
            }
            
            self.ws.send(json.dumps(subscribe_msg))
            logger.debug(f"Subscribed to {market_id} {outcome}")
        
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

