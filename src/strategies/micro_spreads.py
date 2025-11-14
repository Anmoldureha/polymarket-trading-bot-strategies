"""Strategy 2: Farming micro-spreads (buy at 5¢, sell at 6¢)"""

from typing import Dict, List, Optional
from ..strategies.base_strategy import BaseStrategy
from ..risk.position_tracker import Position
from ..utils.logger import setup_logger
from ..utils.market_analyzer import MarketAnalyzer


logger = setup_logger(__name__)


class MicroSpreadStrategy(BaseStrategy):
    """Farm micro-spreads by buying low and selling high"""
    
    def __init__(self, *args, **kwargs):
        """Initialize micro-spread strategy"""
        super().__init__(*args, **kwargs)
        
        # Strategy parameters
        self.min_buy_price = self.config.get('min_buy_price', 0.05)
        self.max_buy_price = self.config.get('max_buy_price', 0.10)
        self.min_profit_pct = self.config.get('min_profit_pct', 20.0)  # 20% minimum (5¢ -> 6¢ = 20%)
        self.target_profit_pct = self.config.get('target_profit_pct', 120.0)  # Target 120% return
        self.position_size = self.config.get('position_size', 10.0)
        self.max_spread_pct = self.config.get('max_spread_pct', 5.0)  # Max 5% spread to enter
        
        self.analyzer = MarketAnalyzer()
        self.open_orders: Dict[str, Dict] = {}
    
    def scan_opportunities(self) -> List[Dict]:
        """
        Scan order books for micro-spread opportunities.
        
        Returns:
            List of micro-spread opportunities
        """
        opportunities = []
        
        try:
            # Use market cache if available
            if self.market_cache:
                markets = self.market_cache.get_markets(active=True, limit=200)
            else:
                markets = self.polymarket_client.get_markets(active=True, limit=200)
            
            # Ensure markets is a list
            if not isinstance(markets, list):
                logger.warning(f"  [{self.name}] get_markets returned non-list: {type(markets)}")
                return []
            
            # Collect market/outcome pairs for parallel price fetching
            market_outcomes = []
            for market in markets:
                # Ensure market is a dict
                if not isinstance(market, dict):
                    continue
                    
                market_id = market.get('id') or market.get('market_id')
                if not market_id:
                    continue
                
                # Add to parallel fetch list
                for outcome in ["YES", "NO"]:
                    market_outcomes.append((market_id, outcome))
            
            # Fetch prices in parallel if cache available
            if self.market_cache and market_outcomes:
                price_results = self.market_cache.get_prices_parallel(market_outcomes, max_workers=10)
            else:
                price_results = {}
            
            # Process markets with fetched prices
            for market in markets:
                market_id = market.get('id') or market.get('market_id')
                if not market_id:
                    continue
                
                try:
                    # Check both YES and NO outcomes
                    for outcome in ["YES", "NO"]:
                        cache_key = f"{market_id}_{outcome}"
                        if cache_key in price_results:
                            prices = price_results[cache_key]
                        elif self.market_cache:
                            prices = self.market_cache.get_price(market_id, outcome)
                        else:
                            prices = self.polymarket_client.get_best_price(market_id, outcome=outcome)
                        
                        bid = prices.get('bid')
                        ask = prices.get('ask')
                        
                        if not bid or not ask:
                            continue
                        
                        # Check if buy price is in our range
                        if self.min_buy_price <= bid <= self.max_buy_price:
                            # Calculate potential profit
                            profit_info = self.analyzer.calculate_micro_spread_profit(bid, ask)
                            
                            if profit_info['profit_pct'] >= self.min_profit_pct:
                                spread_pct = self.analyzer.calculate_spread(bid, ask)
                                
                                if spread_pct <= self.max_spread_pct:
                                    opportunity = {
                                        'market_id': market_id,
                                        'outcome': outcome,
                                        'buy_price': bid,
                                        'sell_price': ask,
                                        'profit_pct': profit_info['profit_pct'],
                                        'spread_pct': spread_pct,
                                        'market_question': market.get('question')
                                    }
                                    
                                    opportunities.append(opportunity)
                
                except Exception as e:
                    logger.debug(f"Error scanning market {market_id}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"  [{self.name}] Error scanning for micro-spread opportunities: {e}", exc_info=True)
        
        # Sort by profit percentage (highest first)
        opportunities.sort(key=lambda x: x['profit_pct'], reverse=True)
        
        if opportunities:
            logger.debug(f"  [{self.name}] Top opportunity: Market {opportunities[0].get('market_id', 'unknown')[:20]} | Profit: {opportunities[0].get('profit_pct', 0):.2f}% | Buy: ${opportunities[0].get('buy_price', 0):.4f} | Sell: ${opportunities[0].get('sell_price', 0):.4f}")
        
        return opportunities[:10]  # Limit to top 10 opportunities
    
    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        """
        Execute micro-spread trade: buy at bid, sell at ask.
        
        Args:
            opportunity: Micro-spread opportunity
            
        Returns:
            Trade result dictionary
        """
        market_id = opportunity['market_id']
        outcome = opportunity['outcome']
        buy_price = opportunity['buy_price']
        sell_price = opportunity['sell_price']
        
        # Check risk limits
        allowed, reason = self.risk_manager.check_trade_allowed(
            strategy=self.name,
            market_id=market_id,
            size=self.position_size,
            price=buy_price,
            side='buy'
        )
        
        if not allowed:
            logger.debug(f"Micro-spread trade not allowed: {reason}")
            return None
        
        try:
            # Get order coordinator from client if available
            order_coordinator = getattr(self.polymarket_client, '_order_coordinator', None)
            
            # Place buy order
            buy_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome=outcome,
                side='buy',
                size=self.position_size,
                price=buy_price,
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if not buy_order:
                return None
            
            # Immediately place sell order at ask price
            sell_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome=outcome,
                side='sell',
                size=self.position_size,
                price=sell_price,
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if not sell_order:
                # Cancel buy order if sell fails
                if 'order_id' in buy_order:
                    self.polymarket_client.cancel_order(buy_order['order_id'])
                return None
            
            # Track position
            position_id = self._generate_position_id()
            position = Position(
                position_id=position_id,
                market_id=market_id,
                strategy=self.name,
                side='buy',
                size=self.position_size,
                entry_price=buy_price,
                current_price=sell_price,
                metadata={
                    'outcome': outcome,
                    'buy_order_id': buy_order.get('order_id'),
                    'sell_order_id': sell_order.get('order_id'),
                    'expected_profit_pct': opportunity['profit_pct']
                }
            )
            
            self.risk_manager.add_position(position)
            
            # Store order info for tracking
            self.open_orders[position_id] = {
                'buy_order_id': buy_order.get('order_id'),
                'sell_order_id': sell_order.get('order_id'),
                'buy_price': buy_price,
                'sell_price': sell_price
            }
            
            trade_logger.info("=" * 80)
            trade_logger.info(f"🎯 TRADE EXECUTED: Micro-spread | {position_id}")
            trade_logger.info(f"   Market: {market_id[:30]}... | Outcome: {outcome}")
            trade_logger.info(f"   Buy @ ${buy_price:.4f} | Sell @ ${sell_price:.4f}")
            trade_logger.info(f"   Expected Profit: {opportunity['profit_pct']:.2f}%")
            trade_logger.info(f"   Size: ${self.position_size:.2f}")
            trade_logger.info("=" * 80)
            
            return {
                'position_id': position_id,
                'strategy': self.name,
                'market_id': market_id,
                'buy_order': buy_order,
                'sell_order': sell_order,
                'expected_profit_pct': opportunity['profit_pct']
            }
        
        except Exception as e:
            error_logger.error(f"Error executing micro-spread trade: {e}", exc_info=True)
            return None

