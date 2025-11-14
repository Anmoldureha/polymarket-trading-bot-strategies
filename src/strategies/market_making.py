"""Strategy 6: Continuous Market Making with Band-Based Order Management [BETA]

⚠️ BETA STATUS: This strategy is currently under evaluation.
Use with caution and monitor closely. Results may vary.

This strategy maintains orders in bands around the market price, continuously
adjusting as the market moves. Based on the polymarket-marketmaking approach.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ..strategies.base_strategy import BaseStrategy
from ..utils.logger import setup_logger, get_trade_logger, get_error_logger

logger = setup_logger(__name__)
trade_logger = get_trade_logger()
error_logger = get_error_logger()


@dataclass
class Band:
    """Represents a trading band with margins and amounts"""
    min_margin: float  # Minimum margin (percent offset from market price)
    avg_margin: float  # Average margin (target order placement)
    max_margin: float  # Maximum margin (band boundary)
    min_amount: float  # Minimum total size in band
    avg_amount: float  # Target total size in band
    max_amount: float  # Maximum total size in band


@dataclass
class OrderInBand:
    """Represents an order within a band"""
    order_id: str
    price: float
    size: float
    side: str  # 'buy' or 'sell'
    distance_from_mid: float  # Distance from mid price


class MarketMakingStrategy(BaseStrategy):
    """
    Continuous market-making strategy that maintains orders in bands around market price.
    
    ⚠️ BETA: This strategy is under evaluation. Use with caution and monitor closely.
    
    Every second, the bot:
    1. Reads current market price
    2. Cancels orders outside bands or exceeding maxAmount
    3. Places new orders to maintain avgAmount in each band
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize market-making strategy"""
        super().__init__(*args, **kwargs)
        
        # Load bands configuration
        bands_path = self.config.get('bands_file', 'config/bands.json')
        self.bands_config = self._load_bands_config(bands_path)
        
        # Strategy parameters
        self.update_interval = self.config.get('update_interval', 1.0)  # Update every second
        self.market_id = self.config.get('market_id')  # Specific market to trade (optional)
        self.outcome = self.config.get('outcome', 'YES')  # Outcome to trade
        self.min_order_size = self.config.get('min_order_size', 1.0)  # Minimum order size
        
        # Track our orders per market
        self.market_orders: Dict[str, Dict[str, List[OrderInBand]]] = {}  # market_id -> side -> orders
        self.last_update_time: Dict[str, float] = {}  # market_id -> timestamp
        
        # Band configurations
        self.buy_bands: List[Band] = self._parse_bands(self.bands_config.get('buyBands', []))
        self.sell_bands: List[Band] = self._parse_bands(self.bands_config.get('sellBands', []))
        
        # Beta status warning
        is_beta = self.config.get('beta', False)
        if is_beta:
            logger.warning(f"⚠️  [{self.name}] BETA STRATEGY - Under evaluation. Use with caution!")
            trade_logger.warning(f"⚠️  Market Making Strategy is BETA - Monitor closely!")
        
        logger.info(f"[{self.name}] Initialized with {len(self.buy_bands)} buy bands and {len(self.sell_bands)} sell bands")
    
    def _load_bands_config(self, bands_path: str) -> Dict:
        """Load bands configuration from JSON file"""
        path = Path(bands_path)
        
        # Try relative to project root
        if not path.exists():
            path = Path(__file__).parent.parent.parent / bands_path
        
        if not path.exists():
            logger.warning(f"Bands config not found at {bands_path}, using defaults")
            return {
                "buyBands": [{"minMargin": 0.005, "avgMargin": 0.01, "maxMargin": 0.02, 
                             "minAmount": 20.0, "avgAmount": 30.0, "maxAmount": 40.0}],
                "sellBands": [{"minMargin": 0.005, "avgMargin": 0.01, "maxMargin": 0.02,
                               "minAmount": 20.0, "avgAmount": 30.0, "maxAmount": 40.0}],
                "buyLimits": [],
                "sellLimits": []
            }
        
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            error_logger.error(f"Error loading bands config: {e}")
            raise
    
    def _parse_bands(self, bands_list: List[Dict]) -> List[Band]:
        """Parse band configurations into Band objects"""
        parsed = []
        for band_dict in bands_list:
            try:
                band = Band(
                    min_margin=float(band_dict['minMargin']),
                    avg_margin=float(band_dict['avgMargin']),
                    max_margin=float(band_dict['maxMargin']),
                    min_amount=float(band_dict['minAmount']),
                    avg_amount=float(band_dict['avgAmount']),
                    max_amount=float(band_dict['maxAmount'])
                )
                parsed.append(band)
            except KeyError as e:
                logger.warning(f"Invalid band configuration, missing key: {e}")
                continue
        return parsed
    
    def scan_opportunities(self) -> List[Dict]:
        """
        Scan for market-making opportunities.
        Returns markets that need order management.
        """
        opportunities = []
        
        try:
            # If specific market is configured, use that
            if self.market_id:
                markets = [{'id': self.market_id}]
            else:
                # Use market cache if available
                if self.market_cache:
                    markets = self.market_cache.get_markets(active=True, limit=50)
                else:
                    markets = self.polymarket_client.get_markets(active=True, limit=50)
            
            if not isinstance(markets, list):
                logger.warning(f"  [{self.name}] get_markets returned non-list: {type(markets)}")
                return []
            
            for market in markets:
                if not isinstance(market, dict):
                    continue
                
                market_id = market.get('id') or market.get('market_id')
                if not market_id:
                    continue
                
                try:
                    # Get current market price
                    if self.market_cache:
                        prices = self.market_cache.get_price(market_id, outcome=self.outcome)
                    else:
                        prices = self.polymarket_client.get_best_price(market_id, outcome=self.outcome)
                    
                    bid = prices.get('bid')
                    ask = prices.get('ask')
                    
                    if not bid or not ask:
                        continue
                    
                    mid_price = (bid + ask) / 2
                    
                    # Check if we need to update orders for this market
                    last_update = self.last_update_time.get(market_id, 0)
                    time_since_update = time.time() - last_update
                    
                    if time_since_update >= self.update_interval:
                        opportunity = {
                            'market_id': market_id,
                            'outcome': self.outcome,
                            'mid_price': mid_price,
                            'bid': bid,
                            'ask': ask,
                            'needs_update': True
                        }
                        opportunities.append(opportunity)
                
                except Exception as e:
                    logger.debug(f"Error scanning market {market_id}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"  [{self.name}] Error scanning for opportunities: {e}", exc_info=True)
        
        return opportunities
    
    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        """
        Execute market-making: synchronize orders for a market.
        
        This involves:
        1. Getting current open orders
        2. Canceling orders outside bands or exceeding maxAmount
        3. Placing new orders to maintain avgAmount in each band
        """
        market_id = opportunity['market_id']
        outcome = opportunity['outcome']
        mid_price = opportunity['mid_price']
        
        try:
            # Get our current open orders for this market
            open_orders = self._get_open_orders(market_id, outcome)
            
            # Synchronize orders
            cancel_count, place_count = self._synchronize_orders(
                market_id, outcome, mid_price, open_orders
            )
            
            # Update last update time
            self.last_update_time[market_id] = time.time()
            
            if cancel_count > 0 or place_count > 0:
                trade_logger.info(
                    f"🔄 [{self.name}] Market {market_id[:20]}... | "
                    f"Mid: ${mid_price:.4f} | "
                    f"Canceled: {cancel_count} | Placed: {place_count}"
                )
            
            return {
                'position_id': f"{self.name}_{market_id}_{int(time.time())}",
                'strategy': self.name,
                'market_id': market_id,
                'canceled_orders': cancel_count,
                'placed_orders': place_count,
                'mid_price': mid_price
            }
        
        except Exception as e:
            error_logger.error(f"Error executing market-making trade: {e}", exc_info=True)
            return None
    
    def _get_open_orders(self, market_id: str, outcome: str) -> Dict[str, List[Dict]]:
        """Get current open orders from exchange"""
        try:
            orders = self.polymarket_client.get_orders(market_id=market_id, status="open")
            
            # Filter by outcome and organize by side
            buy_orders = []
            sell_orders = []
            
            for order in orders:
                if order.get('outcome') == outcome or order.get('outcome') == 'YES':
                    side = order.get('side', '').lower()
                    if side == 'buy':
                        buy_orders.append(order)
                    elif side == 'sell':
                        sell_orders.append(order)
            
            return {'buy': buy_orders, 'sell': sell_orders}
        
        except Exception as e:
            logger.warning(f"Error getting open orders: {e}")
            return {'buy': [], 'sell': []}
    
    def _synchronize_orders(
        self,
        market_id: str,
        outcome: str,
        mid_price: float,
        open_orders: Dict[str, List[Dict]]
    ) -> Tuple[int, int]:
        """
        Synchronize orders: cancel and place as needed.
        
        Returns:
            Tuple of (canceled_count, placed_count)
        """
        canceled_count = 0
        placed_count = 0
        
        # Process buy orders
        canceled_buy, placed_buy = self._synchronize_side(
            market_id, outcome, mid_price, 'buy', self.buy_bands, open_orders.get('buy', [])
        )
        canceled_count += canceled_buy
        placed_count += placed_buy
        
        # Process sell orders
        canceled_sell, placed_sell = self._synchronize_side(
            market_id, outcome, mid_price, 'sell', self.sell_bands, open_orders.get('sell', [])
        )
        canceled_count += canceled_sell
        placed_count += placed_sell
        
        return canceled_count, placed_count
    
    def _synchronize_side(
        self,
        market_id: str,
        outcome: str,
        mid_price: float,
        side: str,
        bands: List[Band],
        open_orders: List[Dict]
    ) -> Tuple[int, int]:
        """
        Synchronize orders for one side (buy or sell).
        
        Returns:
            Tuple of (canceled_count, placed_count)
        """
        canceled_count = 0
        placed_count = 0
        
        if not bands:
            return canceled_count, placed_count
        
        # Convert orders to OrderInBand objects
        orders_in_bands = self._categorize_orders_to_bands(
            open_orders, mid_price, side, bands
        )
        
        # Step 1: Cancel orders outside bands
        for order in open_orders:
            order_id = order.get('order_id')
            order_price = float(order.get('price', 0))
            
            if not order_id or not order_price:
                continue
            
            # Check if order is outside all bands
            if self._is_order_outside_bands(order_price, mid_price, side, bands):
                try:
                    self.polymarket_client.cancel_order(order_id)
                    canceled_count += 1
                    logger.debug(f"Canceled order {order_id} (outside bands)")
                except Exception as e:
                    logger.warning(f"Error canceling order {order_id}: {e}")
        
        # Step 2: Cancel orders if maxAmount breached
        for i, band in enumerate(bands):
            orders_in_band = orders_in_bands[i]
            total_size = sum(o.size for o in orders_in_band)
            
            if total_size > band.max_amount:
                # Need to cancel some orders
                orders_to_cancel = self._select_orders_to_cancel(
                    orders_in_band, total_size - band.max_amount, i, len(bands)
                )
                
                for order in orders_to_cancel:
                    try:
                        self.polymarket_client.cancel_order(order.order_id)
                        canceled_count += 1
                        logger.debug(f"Canceled order {order.order_id} (maxAmount breach)")
                    except Exception as e:
                        logger.warning(f"Error canceling order {order.order_id}: {e}")
        
        # Step 3: Place new orders to maintain avgAmount
        for i, band in enumerate(bands):
            orders_in_band = orders_in_bands[i]
            total_size = sum(o.size for o in orders_in_band)
            
            if total_size < band.avg_amount:
                # Calculate price for new order
                target_price = self._calculate_target_price(mid_price, side, band.avg_margin)
                
                # Calculate size needed
                size_needed = min(band.avg_amount - total_size, band.max_amount - total_size)
                
                if size_needed >= self.min_order_size:
                    # Check risk limits
                    allowed, reason = self.risk_manager.check_trade_allowed(
                        strategy=self.name,
                        market_id=market_id,
                        size=size_needed,
                        price=target_price,
                        side=side
                    )
                    
                    if allowed:
                        try:
                            order_coordinator = getattr(self.polymarket_client, '_order_coordinator', None)
                            result = self.polymarket_client.place_order(
                                market_id=market_id,
                                outcome=outcome,
                                side=side,
                                size=size_needed,
                                price=target_price,
                                order_coordinator=order_coordinator,
                                strategy=self.name
                            )
                            
                            if result and result.get('order_id'):
                                placed_count += 1
                                logger.debug(
                                    f"Placed {side} order @ ${target_price:.4f} "
                                    f"size {size_needed:.2f} in band {i}"
                                )
                        except Exception as e:
                            logger.warning(f"Error placing order: {e}")
        
        return canceled_count, placed_count
    
    def _categorize_orders_to_bands(
        self,
        orders: List[Dict],
        mid_price: float,
        side: str,
        bands: List[Band]
    ) -> List[List[OrderInBand]]:
        """
        Categorize orders into bands.
        
        Returns:
            List of lists, where each inner list contains orders in that band
        """
        orders_in_bands = [[] for _ in bands]
        
        for order in orders:
            order_price = float(order.get('price', 0))
            order_size = float(order.get('size', 0))
            order_id = order.get('order_id', '')
            
            if not order_price or not order_size:
                continue
            
            # Calculate distance from mid price
            if side == 'buy':
                distance = (mid_price - order_price) / mid_price
            else:  # sell
                distance = (order_price - mid_price) / mid_price
            
            # Find which band this order belongs to
            for i, band in enumerate(bands):
                if band.min_margin <= distance <= band.max_margin:
                    order_in_band = OrderInBand(
                        order_id=order_id,
                        price=order_price,
                        size=order_size,
                        side=side,
                        distance_from_mid=distance
                    )
                    orders_in_bands[i].append(order_in_band)
                    break
        
        return orders_in_bands
    
    def _is_order_outside_bands(
        self,
        order_price: float,
        mid_price: float,
        side: str,
        bands: List[Band]
    ) -> bool:
        """Check if an order is outside all bands"""
        if side == 'buy':
            distance = (mid_price - order_price) / mid_price
        else:  # sell
            distance = (order_price - mid_price) / mid_price
        
        # Check if order is within any band
        for band in bands:
            if band.min_margin <= distance <= band.max_margin:
                return False
        
        return True
    
    def _select_orders_to_cancel(
        self,
        orders_in_band: List[OrderInBand],
        excess_size: float,
        band_index: int,
        total_bands: int
    ) -> List[OrderInBand]:
        """
        Select which orders to cancel when maxAmount is breached.
        
        Rules:
        - Inner band (index 0): Cancel orders closest to market price
        - Outer band (last index): Cancel orders furthest from market price
        - Middle bands: Cancel orders by size (smallest first)
        """
        if not orders_in_band:
            return []
        
        # Sort orders appropriately
        if band_index == 0:
            # Inner band: cancel closest to market (highest distance for buy, lowest for sell)
            orders_sorted = sorted(orders_in_band, key=lambda o: o.distance_from_mid, reverse=True)
        elif band_index == total_bands - 1:
            # Outer band: cancel furthest from market
            orders_sorted = sorted(orders_in_band, key=lambda o: o.distance_from_mid)
        else:
            # Middle band: cancel smallest first
            orders_sorted = sorted(orders_in_band, key=lambda o: o.size)
        
        # Select orders to cancel until we've removed excess_size
        to_cancel = []
        size_canceled = 0.0
        
        for order in orders_sorted:
            if size_canceled >= excess_size:
                break
            to_cancel.append(order)
            size_canceled += order.size
        
        return to_cancel
    
    def _calculate_target_price(self, mid_price: float, side: str, margin: float) -> float:
        """Calculate target price for an order based on margin"""
        if side == 'buy':
            return mid_price * (1 - margin)
        else:  # sell
            return mid_price * (1 + margin)

