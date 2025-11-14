"""Main entry point for PolyHFT trading bot"""

import argparse
import sys
from pathlib import Path

from src.bot import TradingBot
from src.utils.logger import setup_multi_logger, get_trade_logger, get_error_logger


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='PolyHFT - Polymarket High-Frequency Trading Bot')
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )
    parser.add_argument(
        '--paper',
        action='store_true',
        help='Enable paper trading mode (overrides config)'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    parser.add_argument(
        '--main-log-file',
        type=str,
        default='logs/bot.log',
        help='Path to main log file (default: logs/bot.log)'
    )
    parser.add_argument(
        '--trade-log-file',
        type=str,
        default='logs/trades.log',
        help='Path to trade log file (default: logs/trades.log)'
    )
    parser.add_argument(
        '--error-log-file',
        type=str,
        default='logs/errors.log',
        help='Path to error log file (default: logs/errors.log)'
    )
    
    args = parser.parse_args()
    
    # Setup multi-logger system
    setup_multi_logger(
        main_log_file=args.main_log_file,
        trade_log_file=args.trade_log_file,
        error_log_file=args.error_log_file,
        log_level=args.log_level
    )
    
    # Show startup message in trade logger (terminal)
    trade_logger = get_trade_logger()
    trade_logger.info("🚀 PolyHFT Trading Bot Starting...")
    trade_logger.info(f"📊 Trades will be logged to: {args.trade_log_file}")
    trade_logger.info(f"⚠️  Errors will be logged to: {args.error_log_file}")
    trade_logger.info(f"📝 Full logs: {args.main_log_file}")
    trade_logger.info("")
    
    # Import logger for regular logging (file only)
    from src.utils.logger import setup_logger
    logger = setup_logger("PolyHFT", log_level=args.log_level, log_file=args.main_log_file, console=False)
    error_logger = get_error_logger()
    logger.info(f"Multi-logger initialized: main={args.main_log_file}, trades={args.trade_log_file}, errors={args.error_log_file}")
    
    # Check if config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        error_logger.error(f"Configuration file not found: {config_path}")
        trade_logger.info("❌ Configuration file not found. Please create config/config.yaml")
        sys.exit(1)
    
    try:
        # Initialize and run bot
        bot = TradingBot(config_path=str(config_path))
        
        # Override paper trading if specified
        if args.paper:
            bot.polymarket_client.paper_trading = True
            if bot.perpdex_client:
                bot.perpdex_client.paper_trading = True
            logger.info("Paper trading mode enabled via command line")
            trade_logger.info("📝 Paper trading mode enabled")
        
        # Run bot
        bot.run()
    
    except KeyboardInterrupt:
        trade_logger.info("\n🛑 Bot stopped by user")
        logger.info("Bot stopped by user")
    except Exception as e:
        error_logger.error(f"Fatal error: {e}", exc_info=True)
        trade_logger.info(f"❌ Fatal error occurred. Check {args.error_log_file} for details.")
        sys.exit(1)


if __name__ == '__main__':
    main()

