"""Base strategy class"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from ..api.polymarket_client import PolymarketClient
from ..api.perpdex_client import PerpdexClient
from ..risk.risk_manager import RiskManager
from ..utils.logger import setup_logger

if TYPE_CHECKING:
    from ..utils.market_cache import MarketCache

logger = setup_logger(__name__)


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(
        self,
        name: str,
        polymarket_client: PolymarketClient,
        risk_manager: RiskManager,
        config: Dict,
        perpdex_client: Optional[PerpdexClient] = None,
        market_cache: Optional['MarketCache'] = None
    ):
        """
        Initialize base strategy.
        
        Args:
            name: Strategy name
            polymarket_client: Polymarket API client
            risk_manager: Risk manager instance
            config: Strategy-specific configuration
            perpdex_client: Perpdex client (optional, for hedging)
            market_cache: Market cache for parallel fetching (optional)
        """
        self.name = name
        self.polymarket_client = polymarket_client
        self.perpdex_client = perpdex_client
        self.risk_manager = risk_manager
        self.config = config
        self.enabled = config.get('enabled', True)
        self.position_counter = 0
        self.market_cache = market_cache
    
    def _generate_position_id(self) -> str:
        """Generate unique position ID"""
        self.position_counter += 1
        return f"{self.name}_{self.position_counter}_{int(self.position_counter * 1000)}"
    
    @abstractmethod
    def scan_opportunities(self) -> List[Dict]:
        """
        Scan for trading opportunities.
        
        Returns:
            List of opportunity dictionaries
        """
        pass
    
    @abstractmethod
    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        """
        Execute a trade based on an opportunity.
        
        Args:
            opportunity: Opportunity dictionary from scan_opportunities
            
        Returns:
            Trade result dictionary or None if failed
        """
        pass
    
    def run(self) -> List[Dict]:
        """
        Run strategy: scan and execute trades.
        
        Returns:
            List of executed trades
        """
        if not self.enabled:
            logger.debug(f"Strategy {self.name} is disabled")
            return []
        
        import time
        from ..utils.logger import get_error_logger
        error_logger = get_error_logger()
        
        scan_start = time.time()
        logger.debug(f"  [{self.name}] Scanning for opportunities...")
        
        opportunities = self.scan_opportunities()
        scan_time = time.time() - scan_start
        
        logger.debug(f"  [{self.name}] Found {len(opportunities)} opportunities (scan took {scan_time:.2f}s)")
        
        if opportunities:
            # Log summary of top opportunities (debug only)
            for i, opp in enumerate(opportunities[:3]):  # Show top 3
                market_id = opp.get('market_id', 'unknown')[:20]  # Truncate long IDs
                if 'profit_pct' in opp:
                    logger.debug(f"    Opportunity {i+1}: Market {market_id} | Profit: {opp['profit_pct']:.2f}%")
                elif 'current_spread_pct' in opp:
                    logger.debug(f"    Opportunity {i+1}: Market {market_id} | Spread: {opp['current_spread_pct']:.2f}%")
        
        executed_trades = []
        
        if opportunities:
            logger.debug(f"  [{self.name}] Attempting to execute trades on {len(opportunities)} opportunities...")
        
        for i, opportunity in enumerate(opportunities):
            try:
                logger.debug(f"  [{self.name}] Executing trade {i+1}/{len(opportunities)}...")
                result = self.execute_trade(opportunity)
                if result:
                    executed_trades.append(result)
                    logger.debug(f"  [{self.name}] ✓ Trade {i+1} executed successfully")
                else:
                    logger.debug(f"  [{self.name}] Trade {i+1} was not executed (risk check failed or API error)")
            except Exception as e:
                error_logger.error(f"  [{self.name}] ✗ Error executing trade {i+1}: {e}", exc_info=True)
        
        if opportunities and not executed_trades:
            logger.debug(f"  [{self.name}] Found {len(opportunities)} opportunities but executed 0 trades")
        
        return executed_trades
    
    def is_enabled(self) -> bool:
        """Check if strategy is enabled"""
        return self.enabled
    
    def enable(self) -> None:
        """Enable strategy"""
        self.enabled = True
        logger.info(f"Strategy {self.name} enabled")
    
    def disable(self) -> None:
        """Disable strategy"""
        self.enabled = False
        logger.info(f"Strategy {self.name} disabled")

