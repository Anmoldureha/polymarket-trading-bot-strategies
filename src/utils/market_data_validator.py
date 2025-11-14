"""Market data validation and verification utilities"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


class MarketDataValidator:
    """Validates and verifies market data from APIs"""
    
    def __init__(self):
        """Initialize validator"""
        self.validation_stats = {
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
            'last_check': None,
            'errors': []
        }
    
    def validate_markets_response(self, response: Any) -> tuple[bool, str, Optional[List[Dict]]]:
        """
        Validate markets API response.
        
        Args:
            response: API response (can be dict, list, or other)
            
        Returns:
            Tuple of (is_valid, error_message, markets_list)
        """
        self.validation_stats['total_checks'] += 1
        
        if response is None:
            error = "Response is None"
            self._record_error(error)
            return False, error, None
        
        # Check if it's a list
        if isinstance(response, list):
            if len(response) == 0:
                error = "Response is empty list"
                self._record_error(error)
                return False, error, []
            
            # Validate first market structure
            first_market = response[0]
            if not isinstance(first_market, dict):
                error = f"Market items should be dicts, got {type(first_market)}"
                self._record_error(error)
                return False, error, None
            
            # Check for required fields
            if not self._has_market_fields(first_market):
                error = f"Market missing required fields: {first_market.keys()}"
                self._record_error(error)
                return False, error, None
            
            self.validation_stats['passed'] += 1
            self.validation_stats['last_check'] = datetime.now().isoformat()
            logger.debug(f"Validated {len(response)} markets")
            return True, "", response
        
        # Check if it's a dict with data/results/markets key
        if isinstance(response, dict):
            markets = None
            
            # Try common response patterns
            for key in ['data', 'results', 'markets', 'items']:
                if key in response:
                    markets = response[key]
                    break
            
            if markets is None:
                # Maybe the dict itself is a market?
                if self._has_market_fields(response):
                    self.validation_stats['passed'] += 1
                    return True, "", [response]
                
                error = f"Dict response missing expected keys. Got: {list(response.keys())}"
                self._record_error(error)
                return False, error, None
            
            # Recursively validate
            return self.validate_markets_response(markets)
        
        # Unknown type
        error = f"Unexpected response type: {type(response)}"
        self._record_error(error)
        return False, error, None
    
    def validate_orderbook_response(self, response: Any) -> tuple[bool, str, Optional[Dict]]:
        """
        Validate orderbook API response.
        
        Args:
            response: API response
            
        Returns:
            Tuple of (is_valid, error_message, orderbook_dict)
        """
        self.validation_stats['total_checks'] += 1
        
        if response is None:
            error = "Orderbook response is None"
            self._record_error(error)
            return False, error, None
        
        if not isinstance(response, dict):
            error = f"Orderbook should be dict, got {type(response)}"
            self._record_error(error)
            return False, error, None
        
        # Check for bids and asks
        if 'bids' not in response or 'asks' not in response:
            error = f"Orderbook missing bids/asks. Got keys: {list(response.keys())}"
            self._record_error(error)
            return False, error, None
        
        bids = response.get('bids', [])
        asks = response.get('asks', [])
        
        # Validate bid/ask structure
        if not isinstance(bids, list) or not isinstance(asks, list):
            error = f"Bids/asks should be lists. Bids: {type(bids)}, Asks: {type(asks)}"
            self._record_error(error)
            return False, error, None
        
        # Validate first bid/ask if present
        if bids and not self._is_valid_price_level(bids[0]):
            error = f"Invalid bid structure: {bids[0]}"
            self._record_error(error)
            return False, error, None
        
        if asks and not self._is_valid_price_level(asks[0]):
            error = f"Invalid ask structure: {asks[0]}"
            self._record_error(error)
            return False, error, None
        
        self.validation_stats['passed'] += 1
        self.validation_stats['last_check'] = datetime.now().isoformat()
        return True, "", response
    
    def validate_price_response(self, prices: Dict) -> tuple[bool, str]:
        """
        Validate price response.
        
        Args:
            prices: Price dict with bid/ask
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(prices, dict):
            return False, f"Prices should be dict, got {type(prices)}"
        
        bid = prices.get('bid')
        ask = prices.get('ask')
        
        if bid is None and ask is None:
            return False, "Both bid and ask are None"
        
        if bid is not None:
            try:
                float(bid)
            except (ValueError, TypeError):
                return False, f"Invalid bid value: {bid}"
        
        if ask is not None:
            try:
                float(ask)
            except (ValueError, TypeError):
                return False, f"Invalid ask value: {ask}"
        
        if bid and ask and float(bid) >= float(ask):
            return False, f"Bid ({bid}) >= Ask ({ask}) - invalid spread"
        
        return True, ""
    
    def _has_market_fields(self, market: Dict) -> bool:
        """Check if market has required fields"""
        # Check for at least one identifier (Polymarket uses condition_id)
        has_id = any(key in market for key in [
            'id', 'market_id', 'slug', 'condition_id', 
            'question_id', 'market_slug'
        ])
        return has_id
    
    def _is_valid_price_level(self, level: Any) -> bool:
        """Check if price level is valid"""
        if not isinstance(level, dict):
            return False
        
        # Should have price and size
        if 'price' not in level:
            return False
        
        try:
            float(level['price'])
        except (ValueError, TypeError):
            return False
        
        return True
    
    def _record_error(self, error: str) -> None:
        """Record validation error"""
        self.validation_stats['failed'] += 1
        self.validation_stats['errors'].append({
            'error': error,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 100 errors
        if len(self.validation_stats['errors']) > 100:
            self.validation_stats['errors'] = self.validation_stats['errors'][-100:]
    
    def log_response_sample(self, response: Any, endpoint: str, max_items: int = 3) -> None:
        """
        Log a sample of the response for debugging.
        
        Args:
            response: API response
            endpoint: Endpoint name
            max_items: Maximum items to log
        """
        logger.info(f"=== API Response Sample: {endpoint} ===")
        logger.info(f"Type: {type(response)}")
        
        if isinstance(response, list):
            logger.info(f"Length: {len(response)}")
            if len(response) > 0:
                logger.info(f"First item type: {type(response[0])}")
                logger.info(f"First item keys: {list(response[0].keys()) if isinstance(response[0], dict) else 'N/A'}")
                logger.info(f"First item sample: {str(response[0])[:200]}")
        elif isinstance(response, dict):
            logger.info(f"Keys: {list(response.keys())}")
            for key, value in list(response.items())[:max_items]:
                logger.info(f"  {key}: {type(value)} = {str(value)[:100]}")
        else:
            logger.info(f"Value: {str(response)[:200]}")
        
        logger.info("=" * 50)
    
    def get_stats(self) -> Dict:
        """Get validation statistics"""
        success_rate = (
            (self.validation_stats['passed'] / self.validation_stats['total_checks'] * 100)
            if self.validation_stats['total_checks'] > 0 else 0
        )
        
        return {
            **self.validation_stats,
            'success_rate': f"{success_rate:.2f}%",
            'recent_errors': self.validation_stats['errors'][-10:]  # Last 10 errors
        }

