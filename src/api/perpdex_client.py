"""Hyperliquid API client wrapper for hedging operations (using Hyperliquid as Perpdex)"""

import requests
import json
import time
import hashlib
from typing import Dict, List, Optional
from eth_account import Account
from eth_account.messages import encode_defunct
from ..api.auth import AuthManager
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


class PerpdexClient:
    """Client for interacting with Hyperliquid API (used for hedging)"""
    
    BASE_URL = "https://api.hyperliquid.xyz"
    
    def __init__(self, wallet_address: Optional[str] = None, private_key: Optional[str] = None, paper_trading: bool = False):
        """
        Initialize Hyperliquid client.
        
        Args:
            wallet_address: Wallet address (optional, will load from env/config if not provided)
            private_key: Private key (optional, will load from env/config if not provided)
            paper_trading: If True, use paper trading mode
        """
        if wallet_address and private_key:
            self.wallet_address = wallet_address
            self.private_key = private_key
        else:
            creds = AuthManager.get_perpdex_credentials()
            self.wallet_address = creds.get('wallet_address') or creds.get('api_key')  # Support both
            self.private_key = creds.get('private_key')
        
        if not self.wallet_address or not self.private_key:
            raise ValueError("Hyperliquid wallet_address and private_key are required")
        
        # Initialize account from private key
        self.account = Account.from_key(self.private_key)
        if self.account.address.lower() != self.wallet_address.lower():
            logger.warning(f"Wallet address mismatch: config={self.wallet_address}, derived={self.account.address}")
        
        self.paper_trading = paper_trading
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def _sign_l1_action(self, action: dict) -> dict:
        """
        Sign a Hyperliquid L1 action using the wallet's private key.
        Hyperliquid uses a specific signing format for exchange actions.
        
        Args:
            action: Action dictionary to sign
            
        Returns:
            Signed action with signature
        """
        # Hyperliquid signing format
        action_str = json.dumps(action, separators=(',', ':'))
        
        # Create message hash
        message_hash = hashlib.sha256(action_str.encode()).digest()
        
        # Sign with Ethereum account
        message_to_sign = encode_defunct(primitive=message_hash)
        signed = self.account.sign_message(message_to_sign)
        
        # Hyperliquid expects the signature in a specific format
        return {
            'action': action,
            'signature': {
                'r': hex(signed.signature.r),
                's': hex(signed.signature.s),
                'v': signed.signature.v
            },
            'nonce': int(time.time() * 1000),
            'vaultAddress': None
        }
    
    def _request(self, method: str, endpoint: str, signed: bool = False, **kwargs) -> Dict:
        """
        Make API request to Hyperliquid.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            signed: Whether to sign the request (for exchange actions)
            **kwargs: Additional request arguments
            
        Returns:
            Response JSON as dict
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        # For signed exchange requests, use Hyperliquid's signing format
        if signed and method == 'POST' and 'json' in kwargs:
            action = kwargs['json']
            signed_action = self._sign_l1_action(action)
            kwargs['json'] = signed_action
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Hyperliquid API request failed: {method} {endpoint} - {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def get_price(self, symbol: str = "BTC") -> float:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Trading symbol (default: BTC, use "BTC" for Hyperliquid)
            
        Returns:
            Current price
        """
        if self.paper_trading:
            # Mock price for paper trading
            return 45000.0
        
        # Hyperliquid uses POST /info endpoint for market data
        endpoint = "/info"
        
        # Request all mids
        request_data = {'type': 'allMids'}
        response = self._request('POST', endpoint, json=request_data)
        
        # Hyperliquid returns a dict with coin -> price mapping
        if isinstance(response, dict):
            # Response format: {"BTC": 45000.0, "ETH": 2500.0, ...}
            if symbol in response:
                return float(response[symbol])
            # Try case variations
            for key, value in response.items():
                if key.upper() == symbol.upper():
                    return float(value)
        
        # Fallback: try to get from orderbook
        request_data = {'type': 'l2Book', 'coin': symbol}
        book_response = self._request('POST', endpoint, json=request_data)
        
        if book_response and isinstance(book_response, dict):
            # Try different response formats
            if 'levels' in book_response:
                levels = book_response['levels']
                if levels and len(levels) > 0:
                    bids = levels[0].get('bids', [])
                    asks = levels[0].get('asks', [])
                    if bids and asks:
                        mid_price = (float(bids[0][0]) + float(asks[0][0])) / 2
                        return mid_price
            elif 'bids' in book_response and 'asks' in book_response:
                bids = book_response['bids']
                asks = book_response['asks']
                if bids and asks and len(bids) > 0 and len(asks) > 0:
                    mid_price = (float(bids[0][0]) + float(asks[0][0])) / 2
                    return mid_price
        
        logger.warning(f"Could not get price for {symbol}, returning 0")
        return 0.0
    
    def open_position(self, symbol: str, side: str, size: float, leverage: float = 1.0) -> Dict:
        """
        Open a position on Hyperliquid.
        
        Args:
            symbol: Trading symbol (e.g., BTC)
            side: 'long' or 'short' (use 'A' for long, 'B' for short in Hyperliquid)
            size: Position size in USD
            leverage: Leverage multiplier
            
        Returns:
            Position response dictionary
        """
        if self.paper_trading:
            price = self.get_price(symbol)
            logger.info(f"[PAPER] Opening {side} position: {size} {symbol} @ {price}")
            return {
                'position_id': f'paper_{symbol}_{side}_{int(time.time())}',
                'symbol': symbol,
                'side': side,
                'size': size,
                'entry_price': price,
                'status': 'open',
                'paper_trading': True
            }
        
        # Get current price for limit order
        current_price = self.get_price(symbol)
        if not current_price:
            raise ValueError(f"Could not get price for {symbol}")
        
        # Hyperliquid order format
        # Size needs to be in the correct format (sz is size in USD, isBuy is True for long)
        is_buy = side.lower() == 'long'
        
        # Hyperliquid uses /exchange endpoint for orders
        endpoint = "/exchange"
        
        # Build action (this will be signed)
        action = {
            'type': 'order',
            'orders': [{
                'a': int(size * 1e6),  # Size in base units (6 decimals for USD)
                'b': is_buy,  # True for long, False for short
                'p': str(current_price),  # Price
                'r': False,  # Reduce only
                't': {
                    'limit': {
                        'tif': 'Gtc'  # Good till cancel
                    }
                }
            }],
            'grouping': 'na'
        }
        
        # Sign and send order
        response = self._request('POST', endpoint, signed=True, json=action)
        
        if response and 'status' in response and response['status'] == 'ok':
            return {
                'position_id': f"{symbol}_{side}_{int(time.time())}",
                'symbol': symbol,
                'side': side,
                'size': size,
                'entry_price': current_price,
                'status': 'open',
                'response': response
            }
        else:
            logger.error(f"Failed to open position: {response}")
            raise Exception(f"Failed to open position: {response}")
    
    def close_position(self, position_id: str) -> Dict:
        """
        Close a position.
        
        Args:
            position_id: Position identifier
            
        Returns:
            Close position response
        """
        if self.paper_trading:
            logger.info(f"[PAPER] Closing position: {position_id}")
            return {'status': 'closed', 'paper_trading': True}
        
        endpoint = f"/positions/{position_id}"
        return self._request('DELETE', endpoint)
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open positions.
        
        Args:
            symbol: Filter by symbol (optional)
            
        Returns:
            List of positions
        """
        if self.paper_trading:
            return []
        
        endpoint = "/positions"
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return self._request('GET', endpoint, params=params)
    
    def get_position_pnl(self, position_id: str) -> Dict:
        """
        Get P&L for a position.
        
        Args:
            position_id: Position identifier
            
        Returns:
            P&L information
        """
        if self.paper_trading:
            return {'pnl': 0.0, 'pnl_pct': 0.0, 'paper_trading': True}
        
        endpoint = f"/positions/{position_id}/pnl"
        return self._request('GET', endpoint)

