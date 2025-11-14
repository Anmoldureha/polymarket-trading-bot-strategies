"""API credential management and authentication"""

import os
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path


# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)


class AuthManager:
    """Manage API credentials securely"""
    
    @staticmethod
    def get_polymarket_credentials() -> dict:
        """
        Get Polymarket API credentials from environment variables.
        
        Returns:
            Dict with api_key and private_key
        """
        api_key = os.getenv('POLYMARKET_API_KEY')
        private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
        
        if not api_key:
            raise ValueError("POLYMARKET_API_KEY not found in environment variables")
        if not private_key:
            raise ValueError("POLYMARKET_PRIVATE_KEY not found in environment variables")
        
        return {
            'api_key': api_key,
            'private_key': private_key
        }
    
    @staticmethod
    def get_perpdex_credentials() -> dict:
        """
        Get Hyperliquid (Perpdex) credentials from environment variables or config.
        
        Returns:
            Dict with wallet_address and private_key
        """
        # Try environment variables first
        wallet_address = os.getenv('HYPERLIQUID_WALLET_ADDRESS') or os.getenv('PERPDEX_WALLET_ADDRESS')
        private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY') or os.getenv('PERPDEX_PRIVATE_KEY')
        
        # Fallback to old API_KEY format for compatibility
        if not wallet_address:
            wallet_address = os.getenv('PERPDEX_API_KEY')
        if not private_key:
            private_key = os.getenv('PERPDEX_PRIVATE_KEY')
        
        # If still not found, try loading from config file
        if not wallet_address or not private_key:
            try:
                from ..utils.config_loader import ConfigLoader
                # Use default config path
                config_loader = ConfigLoader()
                config = config_loader.config
                perpdex_config = config.get('api', {}).get('perpdex', {})
                if not wallet_address:
                    wallet_address = perpdex_config.get('wallet_address')
                if not private_key:
                    private_key = perpdex_config.get('private_key')
            except Exception as e:
                # Silently fail - config might not be available
                pass
        
        if not wallet_address:
            raise ValueError("HYPERLIQUID_WALLET_ADDRESS or PERPDEX_WALLET_ADDRESS not found")
        if not private_key:
            raise ValueError("HYPERLIQUID_PRIVATE_KEY or PERPDEX_PRIVATE_KEY not found")
        
        return {
            'wallet_address': wallet_address,
            'private_key': private_key
        }
    
    @staticmethod
    def validate_credentials(platform: str) -> bool:
        """
        Validate that credentials exist for a platform.
        
        Args:
            platform: 'polymarket' or 'perpdex'
            
        Returns:
            True if credentials are present
        """
        if platform.lower() == 'polymarket':
            try:
                AuthManager.get_polymarket_credentials()
                return True
            except ValueError:
                return False
        elif platform.lower() == 'perpdex':
            try:
                AuthManager.get_perpdex_credentials()
                return True
            except ValueError:
                return False
        return False

