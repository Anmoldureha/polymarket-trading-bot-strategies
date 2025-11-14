"""Strategy 4: Single-market arbitrage (YES+NO < $1.00)"""

from typing import Dict, List, Optional
from ..strategies.base_strategy import BaseStrategy
from ..risk.position_tracker import Position
from ..utils.logger import setup_logger
from ..utils.market_analyzer import MarketAnalyzer


logger = setup_logger(__name__)


class SingleArbitrageStrategy(BaseStrategy):
    """Single-market arbitrage: buy all outcomes when total < $1.00"""
    
    def __init__(self, *args, **kwargs):
        """Initialize single arbitrage strategy"""
        super().__init__(*args, **kwargs)
        
        # Strategy parameters
        self.max_total_price = self.config.get('max_total_price', 0.99)  # Max 99¢ total
        self.min_profit_pct = self.config.get('min_profit_pct', 1.0)  # Minimum 1% profit
        self.position_size = self.config.get('position_size', 100.0)
        self.require_clear_resolution = self.config.get('require_clear_resolution', True)
        
        self.analyzer = MarketAnalyzer()
        self.arbitrage_positions: Dict[str, Dict] = {}
    
    def scan_opportunities(self) -> List[Dict]:
        """
        Scan for markets where YES+NO < $1.00.
        
        Returns:
            List of arbitrage opportunities
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
            
            for market in markets:
                # Ensure market is a dict
                if not isinstance(market, dict):
                    continue
                    
                market_id = market.get('id') or market.get('market_id')
                if not market_id:
                    continue
                
                # Check resolution clarity if required
                if self.require_clear_resolution:
                    resolution_source = market.get('resolution_source', '')
                    if not resolution_source or resolution_source.lower() == 'unknown':
                        continue
                
                try:
                    # Get prices for YES and NO (use cache if available)
                    if self.market_cache:
                        yes_prices = self.market_cache.get_price(market_id, outcome="YES")
                        no_prices = self.market_cache.get_price(market_id, outcome="NO")
                    else:
                        yes_prices = self.polymarket_client.get_best_price(market_id, outcome="YES")
                        no_prices = self.polymarket_client.get_best_price(market_id, outcome="NO")
                    
                    yes_ask = yes_prices.get('ask')
                    no_ask = no_prices.get('ask')
                    
                    if not yes_ask or not no_ask:
                        continue
                    
                    # Check for arbitrage opportunity
                    arb_opp = self.analyzer.find_arbitrage_opportunity(yes_ask, no_ask)
                    
                    if arb_opp and arb_opp['total_price'] <= self.max_total_price:
                        if arb_opp['profit_pct'] >= self.min_profit_pct:
                            opportunity = {
                                'market_id': market_id,
                                'yes_price': yes_ask,
                                'no_price': no_ask,
                                'total_price': arb_opp['total_price'],
                                'profit': arb_opp['profit'],
                                'profit_pct': arb_opp['profit_pct'],
                                'market_question': market.get('question'),
                                'resolution_source': market.get('resolution_source', '')
                            }
                            
                            opportunities.append(opportunity)
                
                except Exception as e:
                    logger.debug(f"Error scanning market {market_id}: {e}")
                    continue
            
            # Also check multi-choice markets
            for market in markets:
                # Ensure market is a dict
                if not isinstance(market, dict):
                    continue
                    
                market_id = market.get('id') or market.get('market_id')
                if not market_id:
                    continue
                
                # Check if it's a multi-choice market
                outcomes = market.get('outcomes', [])
                if len(outcomes) > 2:
                    try:
                        outcome_prices = []
                        for outcome in outcomes:
                            # Ensure outcome is a dict
                            if not isinstance(outcome, dict):
                                continue
                                
                            outcome_token = outcome.get('token_id') or outcome.get('name', '')
                            if outcome_token:
                                prices = self.polymarket_client.get_best_price(market_id, outcome=outcome_token)
                                ask_price = prices.get('ask')
                                if ask_price:
                                    outcome_prices.append(ask_price)
                        
                        if len(outcome_prices) == len(outcomes):
                            arb_opp = self.analyzer.find_multi_choice_arbitrage(outcome_prices)
                            
                            if arb_opp and arb_opp['total_price'] <= self.max_total_price:
                                if arb_opp['profit_pct'] >= self.min_profit_pct:
                                    opportunity = {
                                        'market_id': market_id,
                                        'outcome_prices': outcome_prices,
                                        'outcomes': outcomes,
                                        'total_price': arb_opp['total_price'],
                                        'profit': arb_opp['profit'],
                                        'profit_pct': arb_opp['profit_pct'],
                                        'market_question': market.get('question'),
                                        'multi_choice': True
                                    }
                                    
                                    opportunities.append(opportunity)
                    
                    except Exception as e:
                        logger.debug(f"Error scanning multi-choice market {market_id}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"  [{self.name}] Error scanning for arbitrage opportunities: {e}", exc_info=True)
        
        # Sort by profit percentage (highest first)
        opportunities.sort(key=lambda x: x['profit_pct'], reverse=True)
        
        if opportunities:
            logger.debug(f"  [{self.name}] Top opportunity: Market {opportunities[0].get('market_id', 'unknown')[:20]} | Profit: {opportunities[0].get('profit_pct', 0):.2f}% | Total cost: ${opportunities[0].get('total_price', 0):.4f}")
        
        return opportunities
    
    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        """
        Execute arbitrage: buy all outcomes simultaneously.
        
        Args:
            opportunity: Arbitrage opportunity
            
        Returns:
            Trade result dictionary
        """
        market_id = opportunity['market_id']
        
        # Check if it's a multi-choice market
        if opportunity.get('multi_choice'):
            return self._execute_multi_choice_arbitrage(opportunity)
        else:
            return self._execute_binary_arbitrage(opportunity)
    
    def _execute_binary_arbitrage(self, opportunity: Dict) -> Optional[Dict]:
        """Execute binary market arbitrage (YES/NO)"""
        market_id = opportunity['market_id']
        yes_price = opportunity['yes_price']
        no_price = opportunity['no_price']
        
        # Check risk limits for both sides
        allowed_yes, reason_yes = self.risk_manager.check_trade_allowed(
            strategy=self.name,
            market_id=market_id,
            size=self.position_size,
            price=yes_price,
            side='buy'
        )
        
        allowed_no, reason_no = self.risk_manager.check_trade_allowed(
            strategy=self.name,
            market_id=market_id,
            size=self.position_size,
            price=no_price,
            side='buy'
        )
        
        if not allowed_yes or not allowed_no:
            logger.debug(f"Arbitrage trade not allowed: yes={reason_yes}, no={reason_no}")
            return None
        
        try:
            # Get order coordinator from client if available
            order_coordinator = getattr(self.polymarket_client, '_order_coordinator', None)
            
            # Place YES order
            yes_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome="YES",
                side='buy',
                size=self.position_size,
                price=yes_price,
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if not yes_order:
                return None
            
            # Place NO order
            no_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome="NO",
                side='buy',
                size=self.position_size,
                price=no_price,
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if not no_order:
                # Cancel YES order if NO fails
                if 'order_id' in yes_order:
                    self.polymarket_client.cancel_order(yes_order['order_id'])
                return None
            
            # Track position
            position_id = self._generate_position_id()
            
            self.arbitrage_positions[position_id] = {
                'market_id': market_id,
                'yes_order_id': yes_order.get('order_id'),
                'no_order_id': no_order.get('order_id'),
                'yes_price': yes_price,
                'no_price': no_price,
                'total_price': opportunity['total_price'],
                'expected_profit': opportunity['profit'],
                'size': self.position_size
            }
            
            trade_logger.info("=" * 80)
            trade_logger.info(f"🎯 TRADE EXECUTED: Single-market Arbitrage | {position_id}")
            trade_logger.info(f"   Market: {market_id[:30]}...")
            trade_logger.info(f"   YES @ ${yes_price:.4f} | NO @ ${no_price:.4f}")
            trade_logger.info(f"   Total Cost: ${opportunity['total_price']:.4f}")
            trade_logger.info(f"   Expected Profit: ${opportunity['profit']:.4f} ({opportunity['profit_pct']:.2f}%)")
            trade_logger.info(f"   Size: ${self.position_size:.2f} per outcome")
            trade_logger.info("=" * 80)
            
            return {
                'position_id': position_id,
                'strategy': self.name,
                'market_id': market_id,
                'yes_order': yes_order,
                'no_order': no_order,
                'expected_profit': opportunity['profit'],
                'expected_profit_pct': opportunity['profit_pct']
            }
        
        except Exception as e:
            error_logger.error(f"Error executing binary arbitrage: {e}", exc_info=True)
            return None
    
    def _execute_multi_choice_arbitrage(self, opportunity: Dict) -> Optional[Dict]:
        """Execute multi-choice market arbitrage"""
        market_id = opportunity['market_id']
        outcomes = opportunity['outcomes']
        outcome_prices = opportunity['outcome_prices']
        
        orders = []
        order_coordinator = getattr(self.polymarket_client, '_order_coordinator', None)
        
        try:
            # Place orders for all outcomes
            for i, outcome in enumerate(outcomes):
                outcome_token = outcome.get('token_id') or outcome.get('name', '')
                price = outcome_prices[i]
                
                # Check risk
                allowed, reason = self.risk_manager.check_trade_allowed(
                    strategy=self.name,
                    market_id=market_id,
                    size=self.position_size,
                    price=price,
                    side='buy'
                )
                
                if not allowed:
                    # Cancel all previous orders
                    for order in orders:
                        if 'order_id' in order:
                            self.polymarket_client.cancel_order(order['order_id'])
                    logger.debug(f"Multi-choice arbitrage not allowed for outcome {outcome_token}: {reason}")
                    return None
                
                order = self.polymarket_client.place_order(
                    market_id=market_id,
                    outcome=outcome_token,
                    side='buy',
                    size=self.position_size,
                    price=price,
                    order_coordinator=order_coordinator,
                    strategy=self.name
                )
                
                if not order:
                    # Cancel all previous orders
                    for prev_order in orders:
                        if 'order_id' in prev_order:
                            self.polymarket_client.cancel_order(prev_order['order_id'])
                    return None
                
                orders.append(order)
            
            # Track position
            position_id = self._generate_position_id()
            
            self.arbitrage_positions[position_id] = {
                'market_id': market_id,
                'orders': orders,
                'outcome_prices': outcome_prices,
                'total_price': opportunity['total_price'],
                'expected_profit': opportunity['profit'],
                'size': self.position_size
            }
            
            trade_logger.info("=" * 80)
            trade_logger.info(f"🎯 TRADE EXECUTED: Multi-choice Arbitrage | {position_id}")
            trade_logger.info(f"   Market: {market_id[:30]}... | Outcomes: {len(outcomes)}")
            trade_logger.info(f"   Total Cost: ${opportunity['total_price']:.4f}")
            trade_logger.info(f"   Expected Profit: ${opportunity['profit']:.4f} ({opportunity['profit_pct']:.2f}%)")
            trade_logger.info(f"   Size: ${self.position_size:.2f} per outcome")
            trade_logger.info("=" * 80)
            
            return {
                'position_id': position_id,
                'strategy': self.name,
                'market_id': market_id,
                'orders': orders,
                'expected_profit': opportunity['profit'],
                'expected_profit_pct': opportunity['profit_pct']
            }
        
        except Exception as e:
            error_logger.error(f"Error executing multi-choice arbitrage: {e}", exc_info=True)
            # Cancel any orders that were placed
            for order in orders:
                if 'order_id' in order:
                    try:
                        self.polymarket_client.cancel_order(order['order_id'])
                    except:
                        pass
            return None

