"""Market data cache with parallel fetching"""

import time
import threading
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


class MarketCache:
    """Shared market cache with parallel price fetching"""
    
    def __init__(self, polymarket_client, cache_ttl: float = 5.0):
        """
        Initialize market cache.
        
        Args:
            polymarket_client: Polymarket client instance
            cache_ttl: Cache time-to-live in seconds
        """
        self.polymarket_client = polymarket_client
        self.cache_ttl = cache_ttl
        self._markets_cache: Optional[List[Dict]] = None
        self._cache_timestamp: float = 0
        self._lock = threading.Lock()
        self._price_cache: Dict[str, Dict] = {}  # market_id_outcome -> prices
        self._price_cache_timestamp: Dict[str, float] = {}
    
    def get_markets(self, active: bool = True, limit: int = 200) -> List[Dict]:
        """
        Get markets (cached).
        
        Args:
            active: Only active markets
            limit: Max markets to return
            
        Returns:
            List of market dictionaries
        """
        with self._lock:
            current_time = time.time()
            
            # Return cached if still valid
            if (self._markets_cache is not None and 
                current_time - self._cache_timestamp < self.cache_ttl):
                return self._markets_cache[:limit]
            
            # Fetch fresh markets
            try:
                result = self.polymarket_client.get_markets(active=active, limit=limit)
                # The client may return a list or a dict with 'markets' key (pagination)
                if isinstance(result, dict):
                    markets = result.get('markets', [])
                else:
                    markets = result
                if markets:
                    self._markets_cache = markets
                    self._cache_timestamp = current_time
                    logger.debug(f"Market cache updated: {len(markets)} markets")
                return markets or []
            except Exception as e:
                logger.error(f"Error fetching markets: {e}")
                # Return stale cache if available
                if self._markets_cache:
                    return self._markets_cache[:limit]
                return []
    
    def get_prices_parallel(
        self, 
        market_outcomes: List[tuple], 
        max_workers: int = 10
    ) -> Dict[str, Dict]:
        """
        Fetch prices for multiple market/outcome pairs in parallel.
        
        Args:
            market_outcomes: List of (market_id, outcome) tuples
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dictionary mapping "market_id_outcome" -> prices dict
        """
        results = {}
        current_time = time.time()
        
        # Filter out cached prices that are still valid
        to_fetch = []
        for market_id, outcome in market_outcomes:
            cache_key = f"{market_id}_{outcome}"
            if (cache_key in self._price_cache and 
                cache_key in self._price_cache_timestamp and
                current_time - self._price_cache_timestamp[cache_key] < self.cache_ttl):
                results[cache_key] = self._price_cache[cache_key]
            else:
                to_fetch.append((market_id, outcome, cache_key))
        
        if not to_fetch:
            return results
        
        # Fetch remaining prices in parallel
        def fetch_price(args):
            market_id, outcome, cache_key = args
            try:
                prices = self.polymarket_client.get_best_price(market_id, outcome=outcome)
                return cache_key, prices
            except Exception as e:
                logger.debug(f"Error fetching price for {market_id} {outcome}: {e}")
                return cache_key, None
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_key = {
                executor.submit(fetch_price, args): args[2] 
                for args in to_fetch
            }
            
            for future in as_completed(future_to_key):
                cache_key, prices = future.result()
                if prices:
                    results[cache_key] = prices
                    self._price_cache[cache_key] = prices
                    self._price_cache_timestamp[cache_key] = time.time()
        
        return results
    
    def get_price(self, market_id: str, outcome: str) -> Optional[Dict]:
        """
        Get price for a single market/outcome (uses cache if available).
        Prefers WebSocket cache when available.
        
        Args:
            market_id: Market identifier
            outcome: Outcome (YES, NO, etc.)
            
        Returns:
            Prices dictionary or None
        """
        cache_key = f"{market_id}_{outcome}"
        current_time = time.time()
        
        # Try WebSocket cache first if available
        if hasattr(self.polymarket_client, 'ws_client') and self.polymarket_client.ws_client:
            ws_cache = self.polymarket_client.ws_client.get_orderbook(market_id, outcome)
            if ws_cache:
                # Convert orderbook to price format
                bids = ws_cache.get('bids', [])
                asks = ws_cache.get('asks', [])
                if bids and asks:
                    best_bid = float(bids[0].get('price', 0)) if isinstance(bids[0], dict) else float(bids[0][0]) if isinstance(bids[0], list) else None
                    best_ask = float(asks[0].get('price', 0)) if isinstance(asks[0], dict) else float(asks[0][0]) if isinstance(asks[0], list) else None
                    if best_bid and best_ask:
                        prices = {'bid': best_bid, 'ask': best_ask, 'spread': best_ask - best_bid}
                        self._price_cache[cache_key] = prices
                        self._price_cache_timestamp[cache_key] = current_time
                        return prices
        
        # Check cache first
        if (cache_key in self._price_cache and 
            cache_key in self._price_cache_timestamp and
            current_time - self._price_cache_timestamp[cache_key] < self.cache_ttl):
            return self._price_cache[cache_key]
        
        # Fetch fresh price (will use WebSocket if enabled via adapter)
        try:
            prices = self.polymarket_client.get_best_price(market_id, outcome=outcome)
            if prices:
                self._price_cache[cache_key] = prices
                self._price_cache_timestamp[cache_key] = current_time
                
                # Subscribe to WebSocket if available
                if hasattr(self.polymarket_client, 'ws_client') and self.polymarket_client.ws_client:
                    if self.polymarket_client.ws_client.is_connected():
                        # Pass rest_client to get asset_ids for subscription
                        rest_client = getattr(self.polymarket_client, 'rest_client', None)
                        self.polymarket_client.ws_client.subscribe_orderbook(market_id, outcome, rest_client=rest_client)
            return prices
        except Exception as e:
            logger.debug(f"Error fetching price for {market_id} {outcome}: {e}")
            return None
    
    def clear_cache(self):
        """Clear all caches"""
        with self._lock:
            self._markets_cache = None
            self._cache_timestamp = 0
            self._price_cache.clear()
            self._price_cache_timestamp.clear()

