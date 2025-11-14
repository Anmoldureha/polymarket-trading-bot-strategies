"""Configuration file loader"""

import yaml
from pathlib import Path
from typing import Dict, Any
import os


class ConfigLoader:
    """Load and manage configuration from YAML files"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize config loader.
        
        Args:
            config_path: Path to config YAML file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f) or {}
        
        # Override with environment variables if present
        self._load_env_overrides()
    
    def _load_env_overrides(self) -> None:
        """Override config values with environment variables"""
        # API credentials from env
        if 'POLYMARKET_API_KEY' in os.environ:
            if 'api' not in self.config:
                self.config['api'] = {}
            if 'polymarket' not in self.config['api']:
                self.config['api']['polymarket'] = {}
            self.config['api']['polymarket']['api_key'] = os.environ['POLYMARKET_API_KEY']
        
        if 'POLYMARKET_PRIVATE_KEY' in os.environ:
            if 'api' not in self.config:
                self.config['api'] = {}
            if 'polymarket' not in self.config['api']:
                self.config['api']['polymarket'] = {}
            self.config['api']['polymarket']['private_key'] = os.environ['POLYMARKET_PRIVATE_KEY']
        
        if 'PERPDEX_API_KEY' in os.environ:
            if 'api' not in self.config:
                self.config['api'] = {}
            if 'perpdex' not in self.config['api']:
                self.config['api']['perpdex'] = {}
            self.config['api']['perpdex']['api_key'] = os.environ['PERPDEX_API_KEY']
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get config value using dot notation (e.g., 'risk.max_position_size').
        
        Args:
            key_path: Dot-separated path to config value
            default: Default value if key not found
            
        Returns:
            Config value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific strategy.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Strategy configuration dict
        """
        return self.get(f'strategies.{strategy_name}', {})
    
    def get_risk_config(self) -> Dict[str, Any]:
        """Get risk management configuration"""
        return self.get('risk', {})

