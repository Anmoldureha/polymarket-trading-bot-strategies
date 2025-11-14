"""Strategy 1: Hedging positions (Polymarket short → Perpdex long)"""

from typing import Dict, List, Optional
from ..strategies.base_strategy import BaseStrategy
from ..risk.position_tracker import Position
from ..utils.logger import setup_logger, get_trade_logger, get_error_logger


logger = setup_logger(__name__)
trade_logger = get_trade_logger()
error_logger = get_error_logger()


class HedgingStrategy(BaseStrategy):
    """Hedge Polymarket positions with Perpdex"""
    
    def __init__(self, *args, **kwargs):
        """Initialize hedging strategy"""
        super().__init__(*args, **kwargs)
        
        if not self.perpdex_client:
            raise ValueError("HedgingStrategy requires Perpdex client")
        
        # Strategy parameters
        self.min_profit_target_pct = self.config.get('min_profit_target_pct', 100.0)
        self.max_profit_target_pct = self.config.get('max_profit_target_pct', 150.0)
        self.btc_market_keywords = self.config.get('btc_market_keywords', ['bitcoin', 'btc', 'crypto'])
        self.position_size = self.config.get('position_size', 100.0)
        
        # Track hedged positions
        self.hedged_positions: Dict[str, Dict] = {}
    
    def scan_opportunities(self) -> List[Dict]:
        """
        Scan for BTC markets on Polymarket that can be hedged.
        
        Returns:
            List of hedging opportunities
        """
        opportunities = []
        
        try:
            # Use market cache if available
            if self.market_cache:
                markets = self.market_cache.get_markets(active=True, limit=100)
            else:
                markets = self.polymarket_client.get_markets(active=True, limit=100)
            
            if not isinstance(markets, list):
                logger.warning(f"  [{self.name}] get_markets returned non-list: {type(markets)}")
                return []
            
            for market in markets:
                # Check if market is BTC-related
                question = market.get('question', '').lower()
                if not any(keyword in question for keyword in self.btc_market_keywords):
                    continue
                
                market_id = market.get('id') or market.get('market_id')
                if not market_id:
                    continue
                
                # Get best prices (use cache if available)
                try:
                    if self.market_cache:
                        prices = self.market_cache.get_price(market_id, outcome="YES")
                    else:
                        prices = self.polymarket_client.get_best_price(market_id, outcome="YES")
                    
                    if prices.get('ask') and prices['ask'] < 0.5:  # Short opportunity if YES < 0.5
                        # Check if we can hedge on Perpdex
                        perpdex_price = self.perpdex_client.get_price("BTC")
                        
                        opportunity = {
                            'market_id': market_id,
                            'market_question': market.get('question'),
                            'polymarket_price': prices['ask'],
                            'perpdex_price': perpdex_price,
                            'side': 'short',  # Short on Polymarket
                            'hedge_side': 'long'  # Long on Perpdex
                        }
                        
                        opportunities.append(opportunity)
                except Exception as e:
                    logger.debug(f"Error scanning market {market_id}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"  [{self.name}] Error scanning for hedging opportunities: {e}", exc_info=True)
        
        if opportunities:
            logger.debug(f"  [{self.name}] Top opportunity: Market {opportunities[0].get('market_id', 'unknown')[:20]} | Poly price: ${opportunities[0].get('polymarket_price', 0):.4f}")
        
        return opportunities
    
    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        """
        Execute hedging trade: short Polymarket, long Perpdex.
        
        Args:
            opportunity: Hedging opportunity
            
        Returns:
            Trade result dictionary
        """
        market_id = opportunity['market_id']
        
        # Check risk limits
        allowed, reason = self.risk_manager.check_trade_allowed(
            strategy=self.name,
            market_id=market_id,
            size=self.position_size,
            price=opportunity['polymarket_price'],
            side='sell'
        )
        
        if not allowed:
            logger.debug(f"Hedging trade not allowed: {reason}")
            return None
        
        try:
            # Get order coordinator from client if available
            order_coordinator = getattr(self.polymarket_client, '_order_coordinator', None)
            
            # Short on Polymarket (sell YES shares)
            poly_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome="YES",
                side='sell',
                size=self.position_size,
                price=opportunity['polymarket_price'],
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if not poly_order:
                return None
            
            # Long on Perpdex
            perpdex_position = self.perpdex_client.open_position(
                symbol="BTC",
                side='long',
                size=self.position_size / opportunity['perpdex_price']  # Convert to BTC amount
            )
            
            if not perpdex_position:
                # Cancel Polymarket order if Perpdex fails
                if 'order_id' in poly_order:
                    self.polymarket_client.cancel_order(poly_order['order_id'])
                return None
            
            # Track position
            position_id = self._generate_position_id()
            position = Position(
                position_id=position_id,
                market_id=market_id,
                strategy=self.name,
                side='sell',
                size=self.position_size,
                entry_price=opportunity['polymarket_price'],
                metadata={
                    'perpdex_position_id': perpdex_position.get('position_id'),
                    'perpdex_entry_price': opportunity['perpdex_price']
                }
            )
            
            self.risk_manager.add_position(position)
            
            # Store hedged position info
            self.hedged_positions[position_id] = {
                'poly_order_id': poly_order.get('order_id'),
                'perpdex_position_id': perpdex_position.get('position_id'),
                'entry_poly_price': opportunity['polymarket_price'],
                'entry_perpdex_price': opportunity['perpdex_price']
            }
            
            trade_logger.info("=" * 80)
            trade_logger.info(f"🎯 TRADE EXECUTED: Hedging Strategy | {position_id}")
            trade_logger.info(f"   Market: {market_id[:30]}...")
            trade_logger.info(f"   Short Polymarket @ ${opportunity['polymarket_price']:.4f}")
            trade_logger.info(f"   Long BTC @ ${opportunity['perpdex_price']:.4f}")
            trade_logger.info(f"   Size: ${self.position_size:.2f}")
            trade_logger.info("=" * 80)
            
            return {
                'position_id': position_id,
                'strategy': self.name,
                'market_id': market_id,
                'poly_order': poly_order,
                'perpdex_position': perpdex_position
            }
        
        except Exception as e:
            error_logger.error(f"Error executing hedging trade: {e}", exc_info=True)
            return None
    
    def check_profit_targets(self) -> List[Dict]:
        """
        Check if any hedged positions have reached profit targets.
        
        Returns:
            List of positions ready to close
        """
        positions_to_close = []
        
        for position_id, hedge_info in self.hedged_positions.items():
            if position_id not in self.risk_manager.position_tracker.positions:
                continue
            
            try:
                # Get current prices
                market_id = self.risk_manager.position_tracker.positions[position_id].market_id
                current_poly_price = self.polymarket_client.get_best_price(market_id, outcome="YES")
                current_perpdex_price = self.perpdex_client.get_price("BTC")
                
                entry_poly = hedge_info['entry_poly_price']
                entry_perpdex = hedge_info['entry_perpdex_price']
                
                # Calculate spread profit
                # If we shorted YES at 0.4 and it goes to 0.2, we profit 0.2
                # If BTC goes up, we profit on the long
                poly_profit = entry_poly - current_poly_price.get('bid', entry_poly)
                perpdex_profit = (current_perpdex_price - entry_perpdex) / entry_perpdex
                
                # Combined profit percentage
                total_profit_pct = (poly_profit / entry_poly) * 100 + perpdex_profit * 100
                
                if self.min_profit_target_pct <= total_profit_pct <= self.max_profit_target_pct:
                    positions_to_close.append({
                        'position_id': position_id,
                        'profit_pct': total_profit_pct,
                        'current_poly_price': current_poly_price,
                        'current_perpdex_price': current_perpdex_price
                    })
            
            except Exception as e:
                logger.debug(f"Error checking profit for {position_id}: {e}")
        
        return positions_to_close

