#!/usr/bin/env python3
"""Test Telegram notifications"""

import sys
import time
from src.utils.telegram_notifier import TelegramNotifier
from src.utils.config_loader import ConfigLoader

def test_telegram():
    """Test Telegram bot functionality"""
    print("=" * 60)
    print("Testing Telegram Integration")
    print("=" * 60)
    
    # Load config
    config = ConfigLoader("config/config.yaml")
    telegram_config = config.config.get('telegram', {})
    bot_token = telegram_config.get('bot_token')
    
    if not bot_token:
        print("❌ ERROR: No Telegram bot token found in config.yaml")
        print("   Please add your bot token to config/config.yaml under 'telegram.bot_token'")
        return False
    
    print(f"✓ Bot token found: {bot_token[:20]}...")
    
    # Initialize notifier
    chat_id = telegram_config.get('chat_id')
    print(f"✓ Initializing Telegram notifier...")
    notifier = TelegramNotifier(bot_token, chat_id)
    
    if not notifier.enabled:
        print("❌ ERROR: Telegram notifier not enabled")
        return False
    
    print("✓ Telegram notifier initialized")
    
    # Check if chat_id is set
    if not notifier.chat_id:
        print("\n⚠️  Chat ID not detected yet!")
        print("\n   To enable notifications:")
        print("   1. Open Telegram app")
        print("   2. Search for your bot (use the username BotFather gave you)")
        print("   3. Send any message to the bot (e.g., '/start' or 'hello')")
        print("   4. The bot will automatically detect your chat ID")
        print("\n   Waiting 15 seconds for you to send a message...")
        print("   (The bot is listening in the background)")
        
        # Wait and check periodically
        for i in range(15):
            time.sleep(1)
            # Also try manual check
            if not notifier.chat_id:
                notifier.check_for_updates()
            if notifier.chat_id:
                print(f"\n✓ Chat ID detected after {i+1} seconds!")
                break
            if i % 5 == 4:
                print(f"   Still waiting... ({i+1}/15 seconds)")
        
        # Check again
        if not notifier.chat_id:
            print("\n❌ Chat ID still not detected.")
            print("\n   Troubleshooting:")
            print("   - Make sure you sent a message to YOUR bot (not BotFather)")
            print("   - Check that the bot token is correct")
            print("   - Try sending '/start' command")
            print("   - Run this test again after sending a message")
            return False
    
    print(f"✓ Chat ID detected: {notifier.chat_id}")
    
    # Test sending messages
    print("\n" + "=" * 60)
    print("Sending Test Messages")
    print("=" * 60)
    
    tests = [
        ("Bot Started", lambda: notifier.bot_started(["micro_spreads", "liquidity"])),
        ("Trade Executed", lambda: notifier.trade_executed(
            "micro_spreads",
            "0x1234567890abcdef1234567890abcdef12345678",
            {"profit_cents": 15.5, "buy_price": 0.45, "sell_price": 0.60}
        )),
        ("Trade Completed", lambda: notifier.trade_completed(
            "micro_spreads",
            "0x1234567890abcdef1234567890abcdef12345678",
            12.50
        )),
        ("Bot Stopped", lambda: notifier.bot_stopped(5, 25.75)),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📤 Testing: {test_name}...", end=" ", flush=True)
        try:
            result = test_func()
            if result:
                print("✓ Sent successfully")
                results.append((test_name, True))
            else:
                print("❌ Failed to send")
                results.append((test_name, False))
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append((test_name, False))
        time.sleep(1)  # Small delay between messages
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, success in results:
        status = "✓ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        print("\n✅ All Telegram tests passed!")
        print("   Check your Telegram app - you should have received 4 test messages.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
    
    return all_passed

if __name__ == "__main__":
    success = test_telegram()
    sys.exit(0 if success else 1)

