"""Polymarket API client wrapper"""

import time
import requests
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from decimal import Decimal
from ..api.auth import AuthManager
from ..api.rate_limiter import RateLimiter, RetryWithBackoff
from ..utils.logger import setup_logger
from ..utils.market_data_validator import MarketDataValidator

if TYPE_CHECKING:
    from ..api.polymarket_websocket import PolymarketWebSocketClient
    from ..core.order_coordinator import OrderCoordinator


logger = setup_logger(__name__)


class PolymarketClient:
    """Client for interacting with Polymarket API"""
    
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self, api_key: Optional[str] = None, private_key: Optional[str] = None, paper_trading: bool = False):
        """
        Initialize Polymarket client.
        
        Args:
            api_key: Polymarket API key (optional, will load from env if not provided)
            private_key: Private key for signing transactions (optional)
            paper_trading: If True, use paper trading mode
        """
        if api_key and private_key:
            self.api_key = api_key
            self.private_key = private_key
        else:
            creds = AuthManager.get_polymarket_credentials()
            self.api_key = creds['api_key']
            self.private_key = creds['private_key']
        
        self.paper_trading = paper_trading
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })
        
        # Rate limiter - conservative defaults (100 calls per 60 seconds)
        self.rate_limiter = RateLimiter(
            max_calls=100,
            period=60.0,
            backoff_factor=2.0,
            max_backoff=300.0
        )
        
        # WebSocket client for real-time data (optional)
        self.ws_client: Optional['PolymarketWebSocketClient'] = None
        self.use_websocket = False  # Can be enabled via config
        
        # Market data validator
        self.validator = MarketDataValidator()
        self.verbose_validation = False  # Set to True for detailed logging
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Make API request with rate limiting and retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request arguments
            
        Returns:
            Response JSON as dict
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        # Log API call
        logger.debug(f"API Call: {method} {endpoint}")
        
        # Wait if rate limit is active
        self.rate_limiter.wait_if_needed(endpoint)
        
        try:
            response = self.session.request(method, url, **kwargs)
            logger.debug(f"API Response: {method} {endpoint} -> {response.status_code}")
            
            # Handle rate limit errors (429)
            if response.status_code == 429:
                self.rate_limiter.handle_rate_limit_error(endpoint)
                # Retry after backoff
                self.rate_limiter.wait_if_needed(endpoint)
                response = self.session.request(method, url, **kwargs)
            
            response.raise_for_status()
            
            # Record successful call
            self.rate_limiter.record_call(endpoint)
            
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                self.rate_limiter.handle_rate_limit_error(endpoint)
                logger.warning(f"Rate limit error for {endpoint}, will retry after backoff")
            logger.error(f"API request failed: {method} {endpoint} - {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {method} {endpoint} - {e}")
            raise
    
    def get_markets(self, active: bool = True, limit: int = 100) -> List[Dict]:
        """
        Get list of markets.
        
        Args:
            active: Only return active markets
            limit: Maximum number of markets to return
            
        Returns:
            List of market dictionaries
        """
        # Always get real markets from Polymarket API
        endpoint = "/markets"
        params = {'active': active, 'limit': limit}
        
        try:
            response = self._request('GET', endpoint, params=params)
            
            # Log raw response for debugging if verbose
            if self.verbose_validation:
                self.validator.log_response_sample(response, endpoint)
            
            # Validate response
            is_valid, error_msg, markets = self.validator.validate_markets_response(response)
            
            if not is_valid:
                logger.error(f"Invalid markets response: {error_msg}")
                logger.error(f"Response type: {type(response)}, value: {str(response)[:500]}")
                return []
            
            if markets is None:
                logger.warning("Validator returned None for markets")
                return []
            
            return markets
            
        except Exception as e:
            logger.error(f"Error fetching markets: {e}", exc_info=True)
            return []
    
    def get_market(self, market_id: str) -> Dict:
        """
        Get details for a specific market.
        
        Args:
            market_id: Market identifier
            
        Returns:
            Market details dictionary
        """
        endpoint = f"/markets/{market_id}"
        return self._request('GET', endpoint)
    
    def enable_websocket(self) -> bool:
        """
        Enable WebSocket for real-time data.
        
        Returns:
            True if WebSocket connected successfully
        """
        if self.ws_client and self.ws_client.is_connected():
            return True
        
        try:
            from ..api.polymarket_websocket import PolymarketWebSocketClient
            self.ws_client = PolymarketWebSocketClient(api_key=self.api_key)
            
            # Set up orderbook update callback
            def on_orderbook_update(market_id, outcome, bids, asks):
                logger.debug(f"Orderbook update: {market_id} {outcome}")
            
            self.ws_client.on_orderbook_update = on_orderbook_update
            
            if self.ws_client.connect():
                self.use_websocket = True
                logger.info("WebSocket enabled for real-time data")
                return True
            else:
                logger.warning("Failed to connect WebSocket, falling back to REST")
                return False
        
        except Exception as e:
            logger.error(f"Error enabling WebSocket: {e}")
            return False
    
    def get_orderbook(self, market_id: str, outcome: str = "YES") -> Dict:
        """
        Get order book for a market outcome.
        
        Args:
            market_id: Market identifier
            outcome: Outcome type (YES, NO, or outcome token ID)
            
        Returns:
            Order book with bids and asks
        """
        # Try WebSocket first if enabled
        if self.use_websocket and self.ws_client and self.ws_client.is_connected():
            cached_orderbook = self.ws_client.get_orderbook(market_id, outcome)
            if cached_orderbook:
                return cached_orderbook
            
            # Subscribe if not already subscribed
            self.ws_client.subscribe_orderbook(market_id, outcome)
            # Wait a bit for first update
            time.sleep(0.5)
            cached_orderbook = self.ws_client.get_orderbook(market_id, outcome)
            if cached_orderbook:
                return cached_orderbook
        
        # Fallback to REST API
        endpoint = f"/book"
        params = {'market': market_id, 'outcome': outcome}
        try:
            response = self._request('GET', endpoint, params=params)
            
            # Log raw response for debugging if verbose
            if self.verbose_validation:
                self.validator.log_response_sample(response, f"{endpoint}?market={market_id}&outcome={outcome}")
            
            # Validate orderbook response
            is_valid, error_msg, orderbook = self.validator.validate_orderbook_response(response)
            
            if not is_valid:
                logger.error(f"Invalid orderbook response for {market_id} {outcome}: {error_msg}")
                logger.error(f"Response: {str(response)[:500]}")
                return {'bids': [], 'asks': []}
            
            if orderbook is None:
                logger.warning(f"Validator returned None for orderbook {market_id} {outcome}")
                return {'bids': [], 'asks': []}
            
            # Log success
            bids_count = len(orderbook.get('bids', []))
            asks_count = len(orderbook.get('asks', []))
            logger.debug(f"Orderbook {market_id} {outcome}: {bids_count} bids, {asks_count} asks")
            
            return orderbook
            
        except Exception as e:
            logger.error(f"Error getting orderbook for {market_id} {outcome}: {e}", exc_info=True)
            return {'bids': [], 'asks': []}
    
    def get_best_price(self, market_id: str, outcome: str = "YES") -> Dict:
        """
        Get best bid and ask prices.
        
        Args:
            market_id: Market identifier
            outcome: Outcome type
            
        Returns:
            Dict with 'bid' and 'ask' prices
        """
        # Always get real prices
        try:
            orderbook = self.get_orderbook(market_id, outcome)
            
            if not isinstance(orderbook, dict):
                return {'bid': None, 'ask': None, 'spread': None}
            
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            best_bid = float(bids[0]['price']) if bids and isinstance(bids[0], dict) else None
            best_ask = float(asks[0]['price']) if asks and isinstance(asks[0], dict) else None
            
            prices = {
                'bid': best_bid,
                'ask': best_ask,
                'spread': best_ask - best_bid if (best_bid and best_ask) else None
            }
            
            # Validate prices
            is_valid, error_msg = self.validator.validate_price_response(prices)
            if not is_valid:
                logger.warning(f"Invalid prices for {market_id} {outcome}: {error_msg}")
            
            return prices
        except Exception as e:
            logger.error(f"Error getting best price for {market_id} {outcome}: {e}", exc_info=True)
            return {'bid': None, 'ask': None, 'spread': None}
    
    def place_order(
        self,
        market_id: str,
        outcome: str,
        side: str,
        size: float,
        price: float,
        order_coordinator: Optional['OrderCoordinator'] = None,
        strategy: str = ""
    ) -> Dict:
        """
        Place a limit order.
        
        Args:
            market_id: Market identifier
            outcome: Outcome type (YES/NO)
            side: 'buy' or 'sell'
            size: Order size in shares
            price: Limit price
            order_coordinator: Order coordinator instance (optional)
            strategy: Strategy name (optional)
            
        Returns:
            Order response dictionary
        """
        if self.paper_trading:
            order_id = f'paper_{market_id}_{side}_{int(time.time() * 1000)}'
            logger.info(f"[PAPER] Placing {side} order: {size} @ {price} on {market_id}")
            
            result = {
                'order_id': order_id,
                'status': 'pending',
                'paper_trading': True
            }
            
            # Register with order coordinator if provided
            if order_coordinator:
                try:
                    order_coordinator.create_order(
                        order_id=order_id,
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
        
        endpoint = "/orders"
        data = {
            'market': market_id,
            'outcome': outcome,
            'side': side,
            'size': str(size),
            'price': str(price)
        }
        
        response = self._request('POST', endpoint, json=data)
        
        # Register with order coordinator if provided
        if order_coordinator and 'order_id' in response:
            try:
                order_coordinator.create_order(
                    order_id=response['order_id'],
                    market_id=market_id,
                    outcome=outcome,
                    side=side,
                    size=size,
                    price=price,
                    strategy=strategy
                )
            except ValueError as e:
                logger.warning(f"Order coordinator rejected order: {e}")
        
        return response
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Cancellation response
        """
        if self.paper_trading:
            logger.info(f"[PAPER] Canceling order: {order_id}")
            return {'status': 'cancelled', 'paper_trading': True}
        
        endpoint = f"/orders/{order_id}"
        return self._request('DELETE', endpoint)
    
    def get_orders(self, market_id: Optional[str] = None, status: str = "open") -> List[Dict]:
        """
        Get user's orders.
        
        Args:
            market_id: Filter by market (optional)
            status: Order status filter (open, filled, cancelled)
            
        Returns:
            List of orders
        """
        if self.paper_trading:
            return []
        
        endpoint = "/orders"
        params = {'status': status}
        if market_id:
            params['market'] = market_id
        
        return self._request('GET', endpoint, params=params)
    
    def get_positions(self, market_id: Optional[str] = None) -> List[Dict]:
        """
        Get user's positions.
        
        Args:
            market_id: Filter by market (optional)
            
        Returns:
            List of positions
        """
        if self.paper_trading:
            return []
        
        endpoint = "/positions"
        params = {}
        if market_id:
            params['market'] = market_id
        
        return self._request('GET', endpoint, params=params)
    
    def get_balance(self) -> Dict:
        """
        Get account balance.
        
        Returns:
            Balance information
        """
        # Always get real balance from API
        endpoint = "/balance"
        try:
            return self._request('GET', endpoint)
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return {'usdc': 0.0, 'error': str(e)}

