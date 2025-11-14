"""Market data analysis utilities"""

from typing import Dict, List, Tuple, Optional
from decimal import Decimal


class MarketAnalyzer:
    """Utilities for analyzing market data and identifying opportunities"""
    
    @staticmethod
    def calculate_spread(bid_price: float, ask_price: float) -> float:
        """
        Calculate bid-ask spread percentage.
        
        Args:
            bid_price: Best bid price
            ask_price: Best ask price
            
        Returns:
            Spread as percentage
        """
        if ask_price == 0:
            return float('inf')
        return ((ask_price - bid_price) / ask_price) * 100
    
    @staticmethod
    def find_arbitrage_opportunity(yes_price: float, no_price: float) -> Optional[Dict]:
        """
        Check if single-market arbitrage opportunity exists.
        
        Args:
            yes_price: YES outcome price
            no_price: NO outcome price
            
        Returns:
            Dict with opportunity details or None
        """
        total_price = yes_price + no_price
        
        if total_price < 1.0:
            profit = 1.0 - total_price
            profit_pct = (profit / total_price) * 100
            
            return {
                'exists': True,
                'yes_price': yes_price,
                'no_price': no_price,
                'total_price': total_price,
                'profit': profit,
                'profit_pct': profit_pct
            }
        
        return None
    
    @staticmethod
    def find_multi_choice_arbitrage(outcome_prices: List[float]) -> Optional[Dict]:
        """
        Check if multi-choice market arbitrage exists.
        
        Args:
            outcome_prices: List of prices for all outcomes
            
        Returns:
            Dict with opportunity details or None
        """
        total_price = sum(outcome_prices)
        
        if total_price < 1.0:
            profit = 1.0 - total_price
            profit_pct = (profit / total_price) * 100
            
            return {
                'exists': True,
                'outcome_prices': outcome_prices,
                'total_price': total_price,
                'profit': profit,
                'profit_pct': profit_pct
            }
        
        return None
    
    @staticmethod
    def calculate_micro_spread_profit(buy_price: float, sell_price: float) -> Dict:
        """
        Calculate profit from micro-spread trade.
        
        Args:
            buy_price: Price to buy at
            sell_price: Price to sell at
            
        Returns:
            Dict with profit metrics
        """
        if buy_price == 0:
            return {'profit_pct': 0, 'profit': 0}
        
        profit = sell_price - buy_price
        profit_pct = (profit / buy_price) * 100
        
        return {
            'buy_price': buy_price,
            'sell_price': sell_price,
            'profit': profit,
            'profit_pct': profit_pct
        }
    
    @staticmethod
    def find_correlated_markets(markets: List[Dict], keyword: str) -> List[Dict]:
        """
        Find markets correlated by keyword/narrative.
        
        Args:
            markets: List of market dicts with 'question' or 'description' fields
            keyword: Keyword to search for
            
        Returns:
            List of correlated markets
        """
        correlated = []
        keyword_lower = keyword.lower()
        
        for market in markets:
            question = market.get('question', '').lower()
            description = market.get('description', '').lower()
            
            if keyword_lower in question or keyword_lower in description:
                correlated.append(market)
        
        return correlated
    
    @staticmethod
    def detect_price_divergence(market1_price: float, market2_price: float, threshold: float = 0.05) -> bool:
        """
        Detect if two correlated markets have diverged significantly.
        
        Args:
            market1_price: Price in first market
            market2_price: Price in second market
            threshold: Minimum divergence threshold (default 5%)
            
        Returns:
            True if divergence detected
        """
        if market1_price == 0 or market2_price == 0:
            return False
        
        divergence = abs(market1_price - market2_price) / max(market1_price, market2_price)
        return divergence >= threshold

