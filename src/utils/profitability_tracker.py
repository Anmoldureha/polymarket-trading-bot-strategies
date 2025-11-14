"""Profitability tracking and analytics"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


@dataclass
class TradeRecord:
    """Record of a completed trade"""
    trade_id: str
    strategy: str
    market_id: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    side: str  # 'buy' or 'sell'
    pnl: float
    pnl_pct: float
    fees: float = 0.0


class ProfitabilityTracker:
    """Track profitability metrics across all strategies"""
    
    def __init__(self):
        """Initialize profitability tracker"""
        self.trades: List[TradeRecord] = []
        self.initial_capital: float = 0.0
        self.current_capital: float = 0.0
        
        # Strategy-specific metrics
        self.strategy_stats: Dict[str, Dict] = defaultdict(lambda: {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'total_pnl_pct': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0
        })
    
    def set_initial_capital(self, capital: float) -> None:
        """Set initial capital"""
        self.initial_capital = capital
        self.current_capital = capital
    
    def record_trade(self, trade: TradeRecord) -> None:
        """
        Record a completed trade.
        
        Args:
            trade: TradeRecord to add
        """
        self.trades.append(trade)
        self.current_capital += trade.pnl
        
        # Update strategy stats
        stats = self.strategy_stats[trade.strategy]
        stats['total_trades'] += 1
        stats['total_pnl'] += trade.pnl
        
        if trade.pnl > 0:
            stats['winning_trades'] += 1
            stats['largest_win'] = max(stats['largest_win'], trade.pnl)
            if stats['avg_win'] == 0:
                stats['avg_win'] = trade.pnl
            else:
                stats['avg_win'] = (stats['avg_win'] * (stats['winning_trades'] - 1) + trade.pnl) / stats['winning_trades']
        else:
            stats['losing_trades'] += 1
            stats['largest_loss'] = min(stats['largest_loss'], trade.pnl)
            if stats['avg_loss'] == 0:
                stats['avg_loss'] = trade.pnl
            else:
                stats['avg_loss'] = (stats['avg_loss'] * (stats['losing_trades'] - 1) + trade.pnl) / stats['losing_trades']
        
        # Calculate win rate
        if stats['total_trades'] > 0:
            stats['win_rate'] = (stats['winning_trades'] / stats['total_trades']) * 100
        
        # Calculate average P&L percentage
        if stats['total_trades'] > 0:
            stats['total_pnl_pct'] = (stats['total_pnl'] / self.initial_capital) * 100
    
    def get_overall_stats(self) -> Dict:
        """
        Get overall profitability statistics.
        
        Returns:
            Dictionary of overall stats
        """
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl < 0)
        
        total_pnl = sum(t.pnl for t in self.trades)
        total_pnl_pct = (total_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0.0
        
        roi = ((self.current_capital - self.initial_capital) / self.initial_capital * 100) if self.initial_capital > 0 else 0.0
        
        winning_pnls = [t.pnl for t in self.trades if t.pnl > 0]
        losing_pnls = [t.pnl for t in self.trades if t.pnl < 0]
        
        avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0.0
        avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0.0
        
        profit_factor = abs(sum(winning_pnls) / sum(losing_pnls)) if losing_pnls and sum(losing_pnls) != 0 else float('inf') if winning_pnls else 0.0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0.0,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'roi': roi,
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': max(winning_pnls) if winning_pnls else 0.0,
            'largest_loss': min(losing_pnls) if losing_pnls else 0.0,
            'profit_factor': profit_factor
        }
    
    def get_strategy_stats(self, strategy: Optional[str] = None) -> Dict:
        """
        Get statistics for a specific strategy or all strategies.
        
        Args:
            strategy: Strategy name (None for all)
            
        Returns:
            Dictionary of strategy stats
        """
        if strategy:
            return self.strategy_stats.get(strategy, {})
        return dict(self.strategy_stats)
    
    def get_recent_trades(self, limit: int = 10) -> List[TradeRecord]:
        """
        Get most recent trades.
        
        Args:
            limit: Number of trades to return
            
        Returns:
            List of recent trades
        """
        return sorted(self.trades, key=lambda t: t.exit_time, reverse=True)[:limit]
    
    def get_performance_summary(self) -> str:
        """
        Get a formatted performance summary.
        
        Returns:
            Formatted string summary
        """
        stats = self.get_overall_stats()
        
        summary = f"""
╔═══════════════════════════════════════════════════════════╗
║              PROFITABILITY SUMMARY                        ║
╠═══════════════════════════════════════════════════════════╣
║ Total Trades:          {stats['total_trades']:>10}                    ║
║ Win Rate:              {stats['win_rate']:>9.2f}%                   ║
║ Winning Trades:        {stats['winning_trades']:>10}                    ║
║ Losing Trades:         {stats['losing_trades']:>10}                    ║
╠═══════════════════════════════════════════════════════════╣
║ Total P&L:             ${stats['total_pnl']:>9.2f}                    ║
║ ROI:                   {stats['roi']:>9.2f}%                   ║
║ Initial Capital:       ${stats['initial_capital']:>9.2f}                    ║
║ Current Capital:       ${stats['current_capital']:>9.2f}                    ║
╠═══════════════════════════════════════════════════════════╣
║ Average Win:           ${stats['avg_win']:>9.2f}                    ║
║ Average Loss:          ${stats['avg_loss']:>9.2f}                    ║
║ Largest Win:           ${stats['largest_win']:>9.2f}                    ║
║ Largest Loss:          ${stats['largest_loss']:>9.2f}                    ║
║ Profit Factor:         {stats['profit_factor']:>9.2f}                    ║
╚═══════════════════════════════════════════════════════════╝
"""
        return summary

