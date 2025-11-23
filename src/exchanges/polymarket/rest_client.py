"""REST API client for Polymarket"""

import time
import requests
from typing import Dict, List, Optional
from ...api.auth import AuthManager
from ...api.rate_limiter import RateLimiter
from ...utils.logger import setup_logger
from ...utils.market_data_validator import MarketDataValidator


logger = setup_logger(__name__)


class PolymarketRESTClient:
    """REST API client for Polymarket"""
    
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self, api_key: Optional[str] = None, private_key: Optional[str] = None, paper_trading: bool = False):
        """
        Initialize REST client.
        
        Args:
            api_key: API key (optional)
            private_key: Private key (optional)
            paper_trading: Paper trading mode
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
        
        # Rate limiter
        self.rate_limiter = RateLimiter(
            max_calls=100,
            period=60.0,
            backoff_factor=2.0,
            max_backoff=300.0
        )
        
        # Validator
        self.validator = MarketDataValidator()
        self.verbose_validation = False
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make API request with rate limiting"""
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
                self.rate_limiter.wait_if_needed(endpoint)
                response = self.session.request(method, url, **kwargs)
            
            response.raise_for_status()
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
        """Get list of markets"""
        endpoint = "/markets"
        params = {'active': active, 'limit': limit}
        
        try:
            response = self._request('GET', endpoint, params=params)
            
            if self.verbose_validation:
                self.validator.log_response_sample(response, endpoint)
            
            is_valid, error_msg, markets = self.validator.validate_markets_response(response)
            
            if not is_valid:
                logger.error(f"Invalid markets response: {error_msg}")
                return []
            
            return markets or []
        except Exception as e:
            logger.error(f"Error fetching markets: {e}", exc_info=True)
            return []
    
    def get_orderbook(self, token_id: str, outcome: str = "YES") -> Dict:
        """Get orderbook for a token
        
        Args:
            token_id: Token ID (not market ID or condition ID)
            outcome: Outcome name (for logging/reference only)
        """
        endpoint = "/book"
        params = {'token_id': token_id}
        
        try:
            response = self._request('GET', endpoint, params=params)
            
            if self.verbose_validation:
                self.validator.log_response_sample(response, f"{endpoint}?token_id={token_id}")
            
            is_valid, error_msg, orderbook = self.validator.validate_orderbook_response(response)
            
            if not is_valid:
                logger.error(f"Invalid orderbook response: {error_msg}")
                return {'bids': [], 'asks': []}
            
            return orderbook or {'bids': [], 'asks': []}
        except Exception as e:
            logger.error(f"Error getting orderbook: {e}", exc_info=True)
            return {'bids': [], 'asks': []}
    
    def place_order(self, market_id: str, outcome: str, side: str, size: float, price: float) -> Dict:
        """Place order"""
        if self.paper_trading:
            order_id = f'paper_{market_id}_{side}_{int(time.time() * 1000)}'
            return {
                'order_id': order_id,
                'status': 'pending',
                'paper_trading': True
            }
        
        endpoint = "/orders"
        data = {
            'market': market_id,
            'outcome': outcome,
            'side': side,
            'size': str(size),
            'price': str(price)
        }
        
        return self._request('POST', endpoint, json=data)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel order"""
        if self.paper_trading:
            return {'status': 'cancelled', 'paper_trading': True}
        
        endpoint = f"/orders/{order_id}"
        return self._request('DELETE', endpoint)
    
    def get_orders(self, market_id: Optional[str] = None, status: str = "open") -> List[Dict]:
        """Get orders"""
        if self.paper_trading:
            return []
        
        endpoint = "/orders"
        params = {'status': status}
        if market_id:
            params['market'] = market_id
        
        return self._request('GET', endpoint, params=params)
    
    def get_positions(self, market_id: Optional[str] = None) -> List[Dict]:
        """Get positions"""
        if self.paper_trading:
            return []
        
        endpoint = "/positions"
        params = {}
        if market_id:
            params['market'] = market_id
        
        return self._request('GET', endpoint, params=params)
    
    def get_balance(self) -> Dict:
        """Get balance"""
        endpoint = "/balance"
        try:
            return self._request('GET', endpoint)
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return {'usdc': 0.0, 'error': str(e)}

