#!/usr/bin/env python3
"""Simple script to run the bot in paper trading mode"""

import sys
import time
import signal
from src.bot import TradingBot
from src.utils.logger import setup_logger

logger = setup_logger('PolyHFT', log_level='INFO')

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print('\n\nStopping bot...')
    if 'bot' in globals():
        bot.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print('=' * 70)
print('PolyHFT Trading Bot - Paper Trading Mode')
print('=' * 70)
print('Starting with $100 initial capital')
print('Using REAL Polymarket market data')
print('Press Ctrl+C to stop')
print('=' * 70)
print()

try:
    bot = TradingBot(config_path='config/config.yaml')
    # Paper trading is set via config, but ensure it's enabled
    if hasattr(bot.polymarket_client, 'rest_client'):
        # Adapter pattern
        bot.polymarket_client.rest_client.paper_trading = True
    else:
        # Old client pattern
        bot.polymarket_client.paper_trading = True
    
    if bot.perpdex_client:
        bot.perpdex_client.paper_trading = True
    
    print(f'✅ Bot initialized')
    print(f'✅ Strategies enabled: {list(bot.strategies.keys())}')
    print(f'✅ Initial capital: ${bot.profitability_tracker.initial_capital:.2f}')
    print()
    print('Starting trading loop...')
    print('-' * 70)
    print()
    
    # Run the bot continuously
    bot.run()
    
except KeyboardInterrupt:
    print('\nStopped by user')
    if 'bot' in locals():
        bot.stop()
except Exception as e:
    print(f'\n❌ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

