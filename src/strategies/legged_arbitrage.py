
from typing import Dict, List, Optional
import time
from .base_strategy import BaseStrategy
from ..utils.market_analyzer import MarketAnalyzer
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

class LeggedArbitrageStrategy(BaseStrategy):
    """
    Legged Arbitrage Strategy (Directional Scalping).
    
    1. Enters a directional position (Leg 1) in volatile markets (e.g. BTC) on dip/signal.
    2. Holds position and waits for market move.
    3. Buys opposite outcome (Leg 2) when (Price_Leg1 + Price_Leg2) < max_total_price (e.g. 0.95).
    4. Locks in risk-free profit.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.logger = logger
        
        # Configuration
        self.keywords = self.config.get('keywords', ['Bitcoin', 'BTC'])
        self.entry_max_price = self.config.get('entry_max_price', 0.30)  # Buy cheap side
        self.min_target_profit_cents = self.config.get('min_target_profit_cents', 0.05)
        self.max_total_cost = self.config.get('max_total_cost', 0.95) # Entry + Hedge < 0.95
        self.position_size = self.config.get('position_size', 10.0)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.20)
        self.max_hold_time_hours = self.config.get('max_hold_time_hours', 48)
        
        self.analyzer = MarketAnalyzer()
        
        # State tracking: market_id -> {status, entry_price, entry_outcome, amount, timestamp}
        self.active_legs: Dict[str, Dict] = {} 
        
    def _restore_state(self):
        """Restore active legs from disk/memory if needed. BaseStrategy/Bot handles main position storage, 
           but we need to know WHICH positions are 'Leg 1' waiting for 'Leg 2'.
           For now, we'll infer from open positions that don't have a matching opposite position.
        """
        # TODO: simpler to track in memory for this session or persistent file.
        # Ideally, we infer "Active Legs" by looking at current positions.
        pass

    def get_open_legs(self) -> Dict[str, Dict]:
        """
        Identify partial positions (Leg 1 only) from RiskManager.
        Returns: Dict of market_id -> position_info
        """
        open_legs = {}
        all_positions = self.risk_manager.get_positions_by_market(self.name)
        
        for market_id, positions in all_positions.items():
            # Check if we have both YES and NO
            has_yes = any(p.outcome == 'YES' for p in positions)
            has_no = any(p.outcome == 'NO' for p in positions)
            
            if has_yes and has_no:
                # Fully hedged/arb'd. Ignore.
                continue
            
            # Found a single leg
            for p in positions:
                open_legs[market_id] = {
                    'entry_price': p.average_price,
                    'outcome': p.outcome,
                    'amount': p.size,
                    'id': p.id,
                    'timestamp': p.timestamp # Assuming position has timestamp
                }
        return open_legs

    def run(self) -> List[Dict]:
        """Run strategy iteration"""
        trades_executed = []
        
        # 1. Update State (Identify Open Legs)
        self.active_legs = self.get_open_legs()
        
        # 2. Manage Open Legs (Look for Hedge/Exit)
        for market_id, leg_info in self.active_legs.items():
            trade = self._manage_open_leg(market_id, leg_info)
            if trade:
                trades_executed.append(trade)
                
        # 3. New Entries (If not at max positions)
        if len(self.active_legs) < self.config.get('max_concurrent_positions', 3):
            new_trades = self.scan_opportunities()
            trades_executed.extend(new_trades)
            
        return trades_executed

    def _manage_open_leg(self, market_id: str, leg_info: Dict) -> Optional[Dict]:
        """Check if we can hedge an open leg for profit"""
        entry_price = leg_info['entry_price']
        my_outcome = leg_info['outcome']
        opp_outcome = 'NO' if my_outcome == 'YES' else 'YES'
        amount = leg_info['amount']
        
        # Get current prices
        prices = self.polymarket_client.get_best_price(market_id)
        if not prices:
            return None
            
        # Check Hedge (Buying Opposite)
        # We need the ASK price of the OPPOSED outcome
        opp_ask = prices['yes_ask'] if opp_outcome == 'YES' else prices['no_ask']
        
        if not opp_ask:
            return None
            
        total_cost = entry_price + opp_ask
        
        # Logic: If Cost(Leg1) + Cost(Leg2) < 1.00 - Target_Profit
        # e.g. 0.25 + 0.45 = 0.70 < 0.95. GREAT!
        
        if total_cost <= self.max_total_cost:
            amount_to_hedge = amount # Match size to lock arb
            
            self.logger.info(f"[{self.name}] 🎯 ARBITRAGE FOUND: {market_id}")
            self.logger.info(f"   Leg 1 ({my_outcome}): {entry_price:.2f} (Owned)")
            self.logger.info(f"   Leg 2 ({opp_outcome}): {opp_ask:.2f} (Current Ask)")
            self.logger.info(f"   Total Cost: {total_cost:.2f} < {self.max_total_cost}")
            self.logger.info(f"   Locked Profit: {1.0 - total_cost:.2f} per share")

            # Execute Leg 2
            order = {
                'market_id': market_id,
                'outcome': opp_outcome,
                'side': 'BUY',
                'price': opp_ask, 
                'size': amount_to_hedge,
                'strategy': self.name,
                'comment': 'Legged Arb Close'
            }
            return self.polymarket_client.place_order(order)
            
        # Check Stop Loss (on the held leg)
        # If current bid of my leg < limit, sell.
        my_bid = prices['yes_bid'] if my_outcome == 'YES' else prices['no_bid']
        if my_bid and my_bid < entry_price * (1 - self.stop_loss_pct):
             self.logger.warning(f"[{self.name}] 🛑 STOP LOSS: {market_id} | {my_bid} < {entry_price}")
             # Sell logic would go here (close position)
             return self.risk_manager.close_position(leg_info['id'], my_bid)
             
        return None

    def scan_opportunities(self) -> List[Dict]:
        """Scan for new Leg 1 entries (Implements abstract method)"""
        # Use keywords to find markets
        markets = self.market_cache.get_markets(limit=20) # Simplified scan
        candidates = []
        
        for market in markets:
            # Filter by keyword
            q = market.get('question', '')
            if not any(k.lower() in q.lower() for k in self.keywords):
                continue
                
            if market.get('id') in self.active_legs:
                continue
                
            # Filter by price (Buy the Dip logic / Cheap side)
            # This is a random walk strategy: buy cheap, hope for volatility.
            prices = self.polymarket_client.get_best_price(market['id'])
            if not prices: continue
            
            yes_ask = prices.get('yes_ask')
            no_ask = prices.get('no_ask')
            
            # Strategy: Buy the side < entry_max_price (e.g. 0.25)
            target_side = None
            target_price = 0
            
            if yes_ask and yes_ask <= self.entry_max_price:
                target_side = 'YES'
                target_price = yes_ask
            elif no_ask and no_ask <= self.entry_max_price:
                target_side = 'NO'
                target_price = no_ask
                
            if target_side:
                self.logger.info(f"[{self.name}] 🎲 New Entry: {q} | {target_side} @ {target_price}")
                
                # Check with risk manager before creating opportunity
                if self.risk_manager.can_open_position(self.name, market['id'], self.position_size):
                    opportunity = {
                        'market_id': market['id'],
                        'outcome': target_side,
                        'side': 'BUY',
                        'price': target_price,
                        'size': self.position_size,
                        'strategy': self.name,
                        'comment': 'Legged Arb Entry'
                    }
                    candidates.append(opportunity)
                    return candidates # Single entry per cycle
                
        return []
    
    def execute_trade(self, opportunity: Dict) -> Dict:
        """Execute trade (Implements abstract method)"""
        return self.polymarket_client.place_order(opportunity)

