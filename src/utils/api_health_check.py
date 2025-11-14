"""API health check and connectivity verification"""

import time
from typing import Dict, List, Optional
from datetime import datetime
from ..api.polymarket_client import PolymarketClient
from ..utils.logger import setup_logger
from ..utils.market_data_validator import MarketDataValidator


logger = setup_logger(__name__)


class APIHealthCheck:
    """Check API connectivity and data quality"""
    
    def __init__(self, polymarket_client: PolymarketClient):
        """
        Initialize health checker.
        
        Args:
            polymarket_client: Polymarket client instance
        """
        self.client = polymarket_client
        self.validator = MarketDataValidator()
        self.client.verbose_validation = True  # Enable verbose logging for health checks
    
    def run_full_check(self) -> Dict:
        """
        Run comprehensive API health check.
        
        Returns:
            Health check results dictionary
        """
        logger.info("=" * 60)
        logger.info("Starting API Health Check")
        logger.info("=" * 60)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'api_connectivity': self._check_connectivity(),
            'markets_endpoint': self._check_markets_endpoint(),
            'orderbook_endpoint': self._check_orderbook_endpoint(),
            'price_endpoint': self._check_price_endpoint(),
            'rate_limiter_stats': self._get_rate_limiter_stats(),
            'validation_stats': self.validator.get_stats(),
            'overall_status': 'unknown'
        }
        
        # Determine overall status
        all_passed = all([
            results['api_connectivity']['status'] == 'ok',
            results['markets_endpoint']['status'] == 'ok',
            results['orderbook_endpoint']['status'] == 'ok',
            results['price_endpoint']['status'] == 'ok'
        ])
        
        results['overall_status'] = 'healthy' if all_passed else 'unhealthy'
        
        # Print summary
        self._print_summary(results)
        
        # Disable verbose validation after check
        self.client.verbose_validation = False
        
        return results
    
    def _check_connectivity(self) -> Dict:
        """Check basic API connectivity"""
        logger.info("\n[1/4] Checking API Connectivity...")
        
        try:
            # Try a simple request
            start_time = time.time()
            response = self.client._request('GET', '/markets', params={'limit': 1})
            elapsed = time.time() - start_time
            
            if response is not None:
                logger.info(f"✓ API is reachable (response time: {elapsed:.2f}s)")
                return {
                    'status': 'ok',
                    'response_time_ms': elapsed * 1000,
                    'message': 'API is reachable'
                }
            else:
                logger.error("✗ API returned None")
                return {
                    'status': 'error',
                    'message': 'API returned None'
                }
        except Exception as e:
            logger.error(f"✗ API connectivity failed: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _check_markets_endpoint(self) -> Dict:
        """Check markets endpoint"""
        logger.info("\n[2/4] Checking Markets Endpoint...")
        
        try:
            markets = self.client.get_markets(active=True, limit=10)
            
            if not markets:
                logger.error("✗ No markets returned")
                return {
                    'status': 'error',
                    'markets_count': 0,
                    'message': 'No markets returned'
                }
            
            if not isinstance(markets, list):
                logger.error(f"✗ Markets is not a list: {type(markets)}")
                return {
                    'status': 'error',
                    'markets_count': 0,
                    'message': f'Expected list, got {type(markets)}'
                }
            
            # Validate first market
            if len(markets) > 0:
                first_market = markets[0]
                logger.info(f"✓ Retrieved {len(markets)} markets")
                logger.info(f"  Sample market ID: {first_market.get('id') or first_market.get('market_id')}")
                logger.info(f"  Sample market keys: {list(first_market.keys())[:10]}")
            
            return {
                'status': 'ok',
                'markets_count': len(markets),
                'message': f'Successfully retrieved {len(markets)} markets'
            }
            
        except Exception as e:
            logger.error(f"✗ Markets endpoint failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _check_orderbook_endpoint(self) -> Dict:
        """Check orderbook endpoint"""
        logger.info("\n[3/4] Checking Orderbook Endpoint...")
        
        try:
            # First get a market
            markets = self.client.get_markets(active=True, limit=5)
            if not markets:
                return {
                    'status': 'error',
                    'message': 'Cannot test orderbook - no markets available'
                }
            
            # Try to get orderbook for first market
            market_id = markets[0].get('id') or markets[0].get('market_id')
            if not market_id:
                return {
                    'status': 'error',
                    'message': 'Market missing ID field'
                }
            
            orderbook = self.client.get_orderbook(market_id, outcome="YES")
            
            if not orderbook:
                logger.error("✗ Orderbook is None or empty")
                return {
                    'status': 'error',
                    'message': 'Orderbook is None or empty'
                }
            
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            logger.info(f"✓ Orderbook retrieved for {market_id}")
            logger.info(f"  Bids: {len(bids)}, Asks: {len(asks)}")
            
            if bids:
                logger.info(f"  Best bid: {bids[0]}")
            if asks:
                logger.info(f"  Best ask: {asks[0]}")
            
            return {
                'status': 'ok',
                'market_id': market_id,
                'bids_count': len(bids),
                'asks_count': len(asks),
                'message': f'Orderbook retrieved: {len(bids)} bids, {len(asks)} asks'
            }
            
        except Exception as e:
            logger.error(f"✗ Orderbook endpoint failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _check_price_endpoint(self) -> Dict:
        """Check price endpoint"""
        logger.info("\n[4/4] Checking Price Endpoint...")
        
        try:
            # Get a market
            markets = self.client.get_markets(active=True, limit=5)
            if not markets:
                return {
                    'status': 'error',
                    'message': 'Cannot test prices - no markets available'
                }
            
            market_id = markets[0].get('id') or markets[0].get('market_id')
            if not market_id:
                return {
                    'status': 'error',
                    'message': 'Market missing ID field'
                }
            
            prices = self.client.get_best_price(market_id, outcome="YES")
            
            bid = prices.get('bid')
            ask = prices.get('ask')
            
            if bid is None and ask is None:
                logger.error("✗ Both bid and ask are None")
                return {
                    'status': 'error',
                    'message': 'No prices available'
                }
            
            logger.info(f"✓ Prices retrieved for {market_id}")
            logger.info(f"  Bid: {bid}, Ask: {ask}")
            
            if bid and ask:
                spread = ask - bid
                spread_pct = (spread / bid) * 100 if bid > 0 else 0
                logger.info(f"  Spread: ${spread:.4f} ({spread_pct:.2f}%)")
            
            return {
                'status': 'ok',
                'market_id': market_id,
                'bid': bid,
                'ask': ask,
                'message': f'Prices retrieved: Bid={bid}, Ask={ask}'
            }
            
        except Exception as e:
            logger.error(f"✗ Price endpoint failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _get_rate_limiter_stats(self) -> Dict:
        """Get rate limiter statistics"""
        try:
            return self.client.rate_limiter.get_stats()
        except Exception as e:
            logger.debug(f"Error getting rate limiter stats: {e}")
            return {}
    
    def _print_summary(self, results: Dict) -> None:
        """Print health check summary"""
        logger.info("\n" + "=" * 60)
        logger.info("Health Check Summary")
        logger.info("=" * 60)
        
        logger.info(f"Overall Status: {results['overall_status'].upper()}")
        logger.info(f"Timestamp: {results['timestamp']}")
        logger.info("")
        
        logger.info("Endpoint Status:")
        logger.info(f"  Connectivity: {results['api_connectivity']['status']}")
        logger.info(f"  Markets: {results['markets_endpoint']['status']}")
        logger.info(f"  Orderbook: {results['orderbook_endpoint']['status']}")
        logger.info(f"  Prices: {results['price_endpoint']['status']}")
        logger.info("")
        
        if 'validation_stats' in results:
            stats = results['validation_stats']
            logger.info("Validation Stats:")
            logger.info(f"  Total Checks: {stats.get('total_checks', 0)}")
            logger.info(f"  Passed: {stats.get('passed', 0)}")
            logger.info(f"  Failed: {stats.get('failed', 0)}")
            logger.info(f"  Success Rate: {stats.get('success_rate', '0%')}")
        
        logger.info("=" * 60)

