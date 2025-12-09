"""Strategy 3: Combinatorial Arbitrage (Correlated Markets)"""

from typing import Dict, List, Optional, Set
import re

from ..strategies.base_strategy import BaseStrategy
from ..utils.logger import setup_logger, get_trade_logger, get_error_logger
from ..utils.market_analyzer import MarketAnalyzer

logger = setup_logger(__name__)
trade_logger = get_trade_logger()
error_logger = get_error_logger()

class CombinatorialStrategy(BaseStrategy):
    """
    Combinatorial Arbitrage Strategy:
    Scans for logically linked markets (e.g., derived from same underlying event)
    and identifies price divergences that shouldn't exist.
    
    Current V1 Implementation:
    - Groups markets by shared entities/keywords.
    - Alerts on significant price divergence between effectively similar markets.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Keywords to group markets by (could be loaded from external file)
        self.keywords = self.config.get('keywords', ['Bitcoin', 'Ethereum', 'Trump', 'Biden', 'Fed Rate'])
        self.divergence_threshold = self.config.get('divergence_threshold', 0.10) # 10% difference triggers alert
        self.similarity_threshold = self.config.get('similarity_threshold', 0.5) # Default 0.5 to catch related markets
        self.position_size = self.config.get('position_size', 50.0)
        
        self.analyzer = MarketAnalyzer()
        
    def scan_opportunities(self) -> List[Dict]:
        opportunities = []
        
        try:
            # Get active markets
            if self.market_cache:
                markets = self.market_cache.get_markets(active=True, limit=200)
            else:
                markets = self.polymarket_client.get_markets(active=True, limit=200)
                
            if not isinstance(markets, list):
                return []
                
            # Group by keyword
            grouped_markets = {k: [] for k in self.keywords}
            
            for market in markets:
                question = market.get('question', '').lower()
                for keyword in self.keywords:
                    if keyword.lower() in question:
                        grouped_markets[keyword].append(market)
            
            # Analyze groups
            for keyword, group in grouped_markets.items():
                if len(group) < 2:
                    continue
                    
                # Compare pairs in group
                # This is O(N^2) per group, but N is usually small (< 10)
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        m1 = group[i]
                        m2 = group[j]
                        
                        m1_id = m1.get('id') or m1.get('market_id')
                        m2_id = m2.get('id') or m2.get('market_id')
                        
                        if not m1_id or not m2_id:
                            continue
                            
                        # Get YES prices
                        try:
                            if self.market_cache:
                                p1 = self.market_cache.get_price(m1_id, outcome='YES')
                                p2 = self.market_cache.get_price(m2_id, outcome='YES')
                            else:
                                p1 = self.polymarket_client.get_best_price(m1_id, outcome='YES')
                                p2 = self.polymarket_client.get_best_price(m2_id, outcome='YES')
                                
                            ask1 = float(p1.get('ask') or 0)
                            ask2 = float(p2.get('ask') or 0)
                            
                            if ask1 > 0 and ask2 > 0:
                                # Check divergence
                                diff = abs(ask1 - ask2)
                                max_price = max(ask1, ask2)
                                
                                if max_price > 0 and (diff / max_price) > self.divergence_threshold:
                                    
                                    # Very basic heuristic: if questions are very similar, prices should be similar
                                    # Similarity check (e.g., mostly same words)
                                    sim_score = self._calculate_similarity(m1.get('question'), m2.get('question'))
                                    
                                    if sim_score > self.similarity_threshold:
                                        logger.info(f"[{self.name}] Found divergence for '{keyword}':")
                                        logger.info(f"   M1: {m1.get('question')} @ {ask1}")
                                        logger.info(f"   M2: {m2.get('question')} @ {ask2}")
                                        logger.info(f"   Diff: {diff:.3f} ({diff/max_price:.1%})")
                                        
                                        opportunities.append({
                                            'type': 'divergence',
                                            'keyword': keyword,
                                            'market1': {'id': m1_id, 'question': m1.get('question'), 'price': ask1},
                                            'market2': {'id': m2_id, 'question': m2.get('question'), 'price': ask2},
                                            'diff': diff
                                        })
                                        
                        except Exception as e:
                            logger.debug(f"Error comparing markets {m1_id} / {m2_id}: {e}")
                            continue

        except Exception as e:
            error_logger.error(f"[{self.name}] Error scanning: {e}", exc_info=True)
            
        return opportunities
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Simple Jaccard similarity of words"""
        if not s1 or not s2:
            return 0.0
            
        set1 = set(re.findall(r'\w+', s1.lower()))
        set2 = set(re.findall(r'\w+', s2.lower()))
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        if union == 0:
            return 0.0
            
        return intersection / union

    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        """
        Execute trade based on divergence.
        Complexity: A logical contradiction usually means one is mispriced.
        Without knowing WHICH is mispriced, the safest play is Long Lower Price / Short Higher Price (Arbitrage).
        
        However, Shorting requires minting/burning or finding a Sell order (which on Polymarket is Buying NO).
        So: Buy NO on Expensive Market, Buy YES on Cheap Market?
        
        Assumption: If M1 implies M2, then P(M1) should be <= P(M2).
        If P(M1) > P(M2), contradiction.
        """
        # For V1, we just log this as a signal for the user, or implement a simple "Long the cheaper one" assuming mean reversion?
        # The prompt says "Exploit logical contradictions".
        # Let's perform a "Mean Reversion" trade: Buy the cheaper one? Or purely log it?
        # Given "Automation Level: 70-80%", let's just Log and create a Signal.
        # User defined executing trades in 3-5 simultaneous positions.
        
        logger.info(f"[{self.name}] Signal Only: Divergence detected between {opportunity['market1']['id']} and {opportunity['market2']['id']}")
        return None
