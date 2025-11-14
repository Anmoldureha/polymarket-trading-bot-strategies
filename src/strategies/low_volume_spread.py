"""Strategy: Low-volume high-spread market making (split orders)"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..strategies.base_strategy import BaseStrategy
from ..risk.position_tracker import Position
from ..utils.logger import setup_logger, get_trade_logger, get_error_logger


logger = setup_logger(__name__)
trade_logger = get_trade_logger()
error_logger = get_error_logger()


class LowVolumeSpreadStrategy(BaseStrategy):
    """
    Market making strategy for low-volume markets with high spreads.
    
    Strategy:
    1. Find markets with <$10k volume and >10¢ spread
    2. Use split orders to buy both YES and NO for $1
    3. Place limit orders strategically:
       - One side at high price (comfortable holding)
       - Other side at low price (want to sell quickly)
    4. Sum of limit orders > 100¢ ensures profit
    5. Wait for liquidity, then offload
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize low-volume spread strategy"""
        super().__init__(*args, **kwargs)
        
        # Strategy parameters
        self.max_volume_usd = self.config.get('max_volume_usd', 10000.0)  # Max $10k volume
        self.min_spread_cents = self.config.get('min_spread_cents', 10.0)  # Min 10¢ spread
        self.max_market_age_days = self.config.get('max_market_age_days', 7)  # Max 7 days old
        self.split_amount = self.config.get('split_amount', 1.0)  # Split 1 USDC
        self.comfortable_side_price = self.config.get('comfortable_side_price', 0.95)  # 95¢ for comfortable side
        self.quick_sell_price = self.config.get('quick_sell_price', 0.25)  # 25¢ for quick sell
        self.min_profit_cents = self.config.get('min_profit_cents', 5.0)  # Min 5¢ profit
        
        # Track positions
        self.split_positions: Dict[str, Dict] = {}
    
    def scan_opportunities(self) -> List[Dict]:
        """
        Scan for low-volume markets with high spreads.
        
        Returns:
            List of opportunities
        """
        opportunities = []
        
        try:
            # Use market cache if available
            if self.market_cache:
                markets = self.market_cache.get_markets(active=True, limit=500)
            else:
                markets = self.polymarket_client.get_markets(active=True, limit=500)
            
            if not isinstance(markets, list):
                return []
            
            for market in markets:
                if not isinstance(market, dict):
                    continue
                
                market_id = market.get('id') or market.get('market_id')
                if not market_id:
                    continue
                
                # Check market age (newly launched)
                created_at = market.get('created_at') or market.get('createdAt')
                if created_at:
                    try:
                        if isinstance(created_at, str):
                            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        else:
                            created_date = created_at
                        
                        age_days = (datetime.now(created_date.tzinfo) - created_date).days
                        if age_days > self.max_market_age_days:
                            continue
                    except:
                        pass  # Skip age check if can't parse
                
                # Check volume
                volume = market.get('volume') or market.get('volume_usd') or 0.0
                if volume > self.max_volume_usd:
                    continue
                
                # Check spread
                try:
                    if self.market_cache:
                        yes_prices = self.market_cache.get_price(market_id, outcome="YES")
                        no_prices = self.market_cache.get_price(market_id, outcome="NO")
                    else:
                        yes_prices = self.polymarket_client.get_best_price(market_id, outcome="YES")
                        no_prices = self.polymarket_client.get_best_price(market_id, outcome="NO")
                    
                    yes_bid = yes_prices.get('bid', 0)
                    yes_ask = yes_prices.get('ask', 0)
                    no_bid = no_prices.get('bid', 0)
                    no_ask = no_prices.get('ask', 0)
                    
                    if not (yes_bid and yes_ask and no_bid and no_ask):
                        continue
                    
                    # Calculate spreads
                    yes_spread = yes_ask - yes_bid
                    no_spread = no_ask - no_bid
                    max_spread = max(yes_spread, no_spread)
                    
                    # Check if spread is large enough (in cents)
                    spread_cents = max_spread * 100
                    if spread_cents < self.min_spread_cents:
                        continue
                    
                    # Calculate potential profit
                    # If we split $1 into YES+NO, then sell NO at quick_sell_price
                    # We effectively get YES for (1 - quick_sell_price)
                    effective_yes_cost = 1.0 - self.quick_sell_price
                    
                    # If we can sell YES at comfortable_side_price later
                    # Profit = comfortable_side_price - effective_yes_cost
                    potential_profit = self.comfortable_side_price - effective_yes_cost
                    profit_cents = potential_profit * 100
                    
                    if profit_cents < self.min_profit_cents:
                        continue
                    
                    # Determine which side we're comfortable holding
                    # Check market sentiment or use config preference
                    comfortable_side = self.config.get('preferred_side', 'YES')  # Default to YES
                    
                    opportunity = {
                        'market_id': market_id,
                        'market_question': market.get('question', ''),
                        'volume_usd': volume,
                        'spread_cents': spread_cents,
                        'yes_bid': yes_bid,
                        'yes_ask': yes_ask,
                        'no_bid': no_bid,
                        'no_ask': no_ask,
                        'comfortable_side': comfortable_side,
                        'effective_cost': effective_yes_cost,
                        'potential_profit': potential_profit,
                        'profit_cents': profit_cents,
                        'created_at': created_at
                    }
                    
                    opportunities.append(opportunity)
                
                except Exception as e:
                    logger.debug(f"Error scanning market {market_id}: {e}")
                    continue
            
            # Sort by profit (highest first)
            opportunities.sort(key=lambda x: x['profit_cents'], reverse=True)
            
        except Exception as e:
            error_logger.error(f"Error scanning for low-volume spread opportunities: {e}", exc_info=True)
        
        return opportunities[:5]  # Limit to top 5 opportunities
    
    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        """
        Execute split order strategy.
        
        Args:
            opportunity: Low-volume spread opportunity
            
        Returns:
            Trade result dictionary
        """
        market_id = opportunity['market_id']
        comfortable_side = opportunity['comfortable_side']
        
        # Check risk limits
        allowed, reason = self.risk_manager.check_trade_allowed(
            strategy=self.name,
            market_id=market_id,
            size=self.split_amount,
            price=0.5,  # Split price is effectively 50¢ per share
            side='buy'
        )
        
        if not allowed:
            logger.debug(f"Low-volume spread trade not allowed: {reason}")
            return None
        
        try:
            # Get order coordinator
            order_coordinator = getattr(self.polymarket_client, '_order_coordinator', None)
            
            # Step 1: Place split order (buy both YES and NO for $1)
            # Note: This requires Polymarket's split order API
            # For now, we'll simulate by placing two orders simultaneously
            
            # In real implementation, you'd use:
            # split_order = self.polymarket_client.place_split_order(
            #     market_id=market_id,
            #     amount=self.split_amount
            # )
            
            # For now, we'll place limit orders to buy both sides at market
            # This simulates the split order behavior
            
            # Place buy order for comfortable side (we'll hold this)
            comfortable_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome=comfortable_side,
                side='buy',
                size=self.split_amount,
                price=opportunity[f'{comfortable_side.lower()}_ask'],  # Buy at ask
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if not comfortable_order:
                return None
            
            # Place buy order for other side (we'll sell this quickly)
            other_side = 'NO' if comfortable_side == 'YES' else 'YES'
            other_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome=other_side,
                side='buy',
                size=self.split_amount,
                price=opportunity[f'{other_side.lower()}_ask'],  # Buy at ask
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if not other_order:
                # Cancel comfortable order if other fails
                if 'order_id' in comfortable_order:
                    self.polymarket_client.cancel_order(comfortable_order['order_id'])
                return None
            
            # Step 2: Place limit sell order for the side we want to sell quickly
            quick_sell_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome=other_side,
                side='sell',
                size=self.split_amount,
                price=self.quick_sell_price,
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            # Step 3: Place limit sell order for comfortable side (high price, we're okay holding)
            comfortable_sell_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome=comfortable_side,
                side='sell',
                size=self.split_amount,
                price=self.comfortable_side_price,
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            # Track position
            position_id = self._generate_position_id()
            
            self.split_positions[position_id] = {
                'market_id': market_id,
                'comfortable_side': comfortable_side,
                'other_side': other_side,
                'buy_orders': {
                    comfortable_side: comfortable_order.get('order_id'),
                    other_side: other_order.get('order_id')
                },
                'sell_orders': {
                    other_side: quick_sell_order.get('order_id') if quick_sell_order else None,
                    comfortable_side: comfortable_sell_order.get('order_id') if comfortable_sell_order else None
                },
                'effective_cost': opportunity['effective_cost'],
                'potential_profit': opportunity['potential_profit'],
                'volume_usd': opportunity['volume_usd'],
                'spread_cents': opportunity['spread_cents']
            }
            
            trade_logger.info("=" * 80)
            trade_logger.info(f"🎯 TRADE EXECUTED: Low-Volume Spread Strategy | {position_id}")
            trade_logger.info(f"   Market: {market_id[:30]}...")
            trade_logger.info(f"   Volume: ${opportunity['volume_usd']:.2f} | Spread: {opportunity['spread_cents']:.1f}¢")
            trade_logger.info(f"   Split: ${self.split_amount:.2f} → {comfortable_side} + {other_side}")
            trade_logger.info(f"   Quick sell {other_side} @ ${self.quick_sell_price:.2f}")
            trade_logger.info(f"   Hold {comfortable_side} @ ${self.comfortable_side_price:.2f}")
            trade_logger.info(f"   Effective cost: ${opportunity['effective_cost']:.2f}")
            trade_logger.info(f"   Potential profit: ${opportunity['potential_profit']:.2f} ({opportunity['profit_cents']:.1f}¢)")
            trade_logger.info("=" * 80)
            
            return {
                'position_id': position_id,
                'strategy': self.name,
                'market_id': market_id,
                'comfortable_side': comfortable_side,
                'potential_profit': opportunity['potential_profit'],
                'profit_cents': opportunity['profit_cents']
            }
        
        except Exception as e:
            error_logger.error(f"Error executing low-volume spread trade: {e}", exc_info=True)
            return None
    
    def check_liquidity_and_close(self) -> List[Dict]:
        """
        Check if markets have gained liquidity and close positions.
        
        Returns:
            List of closed positions
        """
        closed_positions = []
        
        for position_id, position_info in list(self.split_positions.items()):
            market_id = position_info['market_id']
            
            try:
                # Check current volume
                market = self.polymarket_client.get_market(market_id)
                current_volume = market.get('volume') or market.get('volume_usd') or 0.0
                
                # If volume has increased significantly, consider closing
                original_volume = position_info['volume_usd']
                volume_increase = current_volume / original_volume if original_volume > 0 else 0
                
                # Close if volume increased 5x or more
                if volume_increase >= 5.0:
                    # Check if we can get better prices now
                    comfortable_side = position_info['comfortable_side']
                    
                    if self.market_cache:
                        prices = self.market_cache.get_price(market_id, outcome=comfortable_side)
                    else:
                        prices = self.polymarket_client.get_best_price(market_id, outcome=comfortable_side)
                    
                    current_price = prices.get('bid') or prices.get('ask')
                    
                    # If current price is close to our target, close
                    if current_price and current_price >= self.comfortable_side_price * 0.9:
                        # Cancel remaining orders and close position
                        # (Implementation would cancel orders and sell remaining shares)
                        closed_positions.append({
                            'position_id': position_id,
                            'market_id': market_id,
                            'volume_increase': volume_increase,
                            'final_price': current_price
                        })
            
            except Exception as e:
                logger.debug(f"Error checking liquidity for {position_id}: {e}")
        
        return closed_positions

