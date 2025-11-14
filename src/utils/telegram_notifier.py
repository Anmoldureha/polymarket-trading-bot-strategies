"""Telegram notifications for trading bot"""

import logging
import threading
import asyncio
import concurrent.futures
from typing import Optional
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


class TelegramNotifier:
    """Send notifications to Telegram using python-telegram-bot library"""
    
    def __init__(self, bot_token: str, chat_id: Optional[str] = None):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token from BotFather
            chat_id: Chat ID (optional, will be auto-detected if not provided)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token)
        self.bot = None
        self.application = None
        self._polling_thread = None
        self._event_loop = None
        self._loop_thread = None
        
        if self.enabled:
            try:
                self.bot = Bot(token=bot_token)
                # Start a persistent event loop in a background thread
                self._start_event_loop()
                # Test connection by getting bot info
                try:
                    async def get_bot_info():
                        return await self.bot.get_me()
                    bot_info = self._run_async(get_bot_info())
                    logger.debug(f"Telegram bot connected: @{bot_info.username}")
                except Exception as e:
                    logger.debug(f"Could not verify Telegram bot: {e}")
            except Exception as e:
                logger.debug(f"Failed to initialize Telegram bot: {e}")
                self.enabled = False
    
    def _start_event_loop(self):
        """Start a persistent event loop in a background thread"""
        def run_loop():
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            self._event_loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        # Wait a bit for loop to start
        import time
        time.sleep(0.1)
    
    def _run_async(self, coro):
        """Run an async coroutine in the persistent event loop"""
        if not self._event_loop:
            # Fallback to asyncio.run if loop not available
            return asyncio.run(coro)
        
        future = asyncio.run_coroutine_threadsafe(coro, self._event_loop)
        return future.result(timeout=10)
    
    def check_for_updates(self) -> Optional[str]:
        """Manually check for updates to detect chat_id"""
        if not self.bot or self.chat_id:
            return self.chat_id
        
        try:
            async def _check():
                # Get the last update
                updates = await self.bot.get_updates(offset=-1, limit=1, timeout=1)
                if updates:
                    update = updates[-1]
                    if update.message:
                        chat_id = str(update.message.chat.id)
                        self.chat_id = chat_id
                        logger.info(f"Telegram chat ID detected: {self.chat_id}")
                        # Send confirmation message
                        try:
                            await self.bot.send_message(
                                chat_id=chat_id,
                                text="✅ Bot connected! You will receive trade notifications here."
                            )
                        except:
                            pass  # Chat ID is set, that's what matters
                        return chat_id
                return None
            
            # Use persistent event loop
            return self._run_async(_check())
        except Exception as e:
            logger.debug(f"Error checking for updates: {e}")
            return None
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send message to Telegram.
        
        Args:
            message: Message text
            parse_mode: Parse mode (HTML or Markdown)
            
        Returns:
            True if sent successfully
        """
        if not self.enabled or not self.bot:
            return False
        
        if not self.chat_id:
            # Chat ID not detected yet - user needs to send a message first
            return False
        
        try:
            # Use persistent event loop
            async def _send():
                try:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        parse_mode=parse_mode
                    )
                    return True
                except Exception as e:
                    logger.debug(f"Error in async send: {e}")
                    return False
            
            return self._run_async(_send())
            
        except Exception as e:
            # Log error but don't spam terminal
            logger.debug(f"Error sending Telegram message: {e}", exc_info=True)
            return False
    
    def bot_started(self, strategies: list) -> bool:
        """Notify that bot has started"""
        message = f"🤖 <b>Bot Started</b>\n\n"
        message += f"✅ Strategies: {', '.join(strategies)}\n"
        message += f"📊 Monitoring markets..."
        return self.send_message(message)
    
    def trade_executed(self, strategy: str, market_id: str, details: dict) -> bool:
        """Notify that a trade was executed"""
        message = f"🎯 <b>Trade Executed</b>\n\n"
        message += f"<b>Strategy:</b> {strategy}\n"
        message += f"<b>Market:</b> {market_id[:30]}...\n"
        
        if 'profit_pct' in details:
            message += f"<b>Profit:</b> {details['profit_pct']:.2f}%\n"
        elif 'profit_cents' in details:
            message += f"<b>Profit:</b> {details['profit_cents']:.1f}¢\n"
        
        if 'buy_price' in details and 'sell_price' in details:
            message += f"<b>Buy:</b> ${details['buy_price']:.4f}\n"
            message += f"<b>Sell:</b> ${details['sell_price']:.4f}\n"
        elif 'effective_cost' in details and 'potential_profit' in details:
            message += f"<b>Cost:</b> ${details['effective_cost']:.2f}\n"
            message += f"<b>Potential:</b> ${details['potential_profit']:.2f}\n"
        
        return self.send_message(message)
    
    def trade_completed(self, strategy: str, market_id: str, profit: float) -> bool:
        """Notify that a trade was completed"""
        message = f"✅ <b>Trade Completed</b>\n\n"
        message += f"<b>Strategy:</b> {strategy}\n"
        message += f"<b>Market:</b> {market_id[:30]}...\n"
        message += f"<b>Profit:</b> ${profit:.2f}"
        return self.send_message(message)
    
    def bot_stopped(self, total_trades: int, final_pnl: float) -> bool:
        """Notify that bot has stopped"""
        message = f"🛑 <b>Bot Stopped</b>\n\n"
        message += f"<b>Total Trades:</b> {total_trades}\n"
        message += f"<b>Final P&L:</b> ${final_pnl:.2f}"
        return self.send_message(message)
