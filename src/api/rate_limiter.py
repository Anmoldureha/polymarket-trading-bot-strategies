"""Rate limiting and backoff utilities for API calls"""

import time
import threading
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


class RateLimiter:
    """Rate limiter with exponential backoff"""
    
    def __init__(
        self,
        max_calls: int = 100,
        period: float = 60.0,
        backoff_factor: float = 2.0,
        max_backoff: float = 300.0
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed
            period: Time period in seconds
            backoff_factor: Multiplier for backoff time
            max_backoff: Maximum backoff time in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        
        # Track calls per endpoint
        self.call_history: Dict[str, list] = defaultdict(list)
        self.backoff_until: Dict[str, float] = {}
        self.lock = threading.Lock()
    
    def _clean_old_calls(self, endpoint: str) -> None:
        """Remove calls outside the time window"""
        now = time.time()
        cutoff = now - self.period
        
        with self.lock:
            self.call_history[endpoint] = [
                call_time for call_time in self.call_history[endpoint]
                if call_time > cutoff
            ]
    
    def _get_backoff_time(self, endpoint: str) -> float:
        """Get current backoff time for endpoint"""
        if endpoint not in self.backoff_until:
            return 0.0
        
        backoff_until = self.backoff_until[endpoint]
        if time.time() < backoff_until:
            return backoff_until - time.time()
        
        return 0.0
    
    def _set_backoff(self, endpoint: str, backoff_time: float) -> None:
        """Set backoff time for endpoint"""
        with self.lock:
            current_backoff = self.backoff_until.get(endpoint, 0.0)
            new_backoff = time.time() + min(backoff_time, self.max_backoff)
            self.backoff_until[endpoint] = max(current_backoff, new_backoff)
    
    def _increase_backoff(self, endpoint: str) -> None:
        """Exponentially increase backoff time"""
        current_backoff = self._get_backoff_time(endpoint)
        if current_backoff == 0:
            new_backoff = 1.0  # Start with 1 second
        else:
            new_backoff = current_backoff * self.backoff_factor
        
        self._set_backoff(endpoint, new_backoff)
        logger.warning(f"Rate limit hit for {endpoint}, backing off for {new_backoff:.2f}s")
    
    def _reset_backoff(self, endpoint: str) -> None:
        """Reset backoff after successful call"""
        with self.lock:
            if endpoint in self.backoff_until:
                del self.backoff_until[endpoint]
    
    def wait_if_needed(self, endpoint: str) -> None:
        """
        Wait if rate limit is exceeded or backoff is active.
        
        Args:
            endpoint: API endpoint identifier
        """
        # Check if we're in backoff period
        backoff_time = self._get_backoff_time(endpoint)
        if backoff_time > 0:
            logger.debug(f"Waiting {backoff_time:.2f}s due to backoff for {endpoint}")
            time.sleep(backoff_time)
        
        # Clean old calls
        self._clean_old_calls(endpoint)
        
        # Check if we've exceeded rate limit
        with self.lock:
            call_count = len(self.call_history[endpoint])
        
        if call_count >= self.max_calls:
            wait_time = self.period - (time.time() - self.call_history[endpoint][0])
            if wait_time > 0:
                logger.warning(f"Rate limit reached for {endpoint}, waiting {wait_time:.2f}s")
                time.sleep(wait_time)
                self._clean_old_calls(endpoint)
    
    def record_call(self, endpoint: str) -> None:
        """Record an API call"""
        with self.lock:
            self.call_history[endpoint].append(time.time())
        
        # Reset backoff on successful call
        self._reset_backoff(endpoint)
    
    def handle_rate_limit_error(self, endpoint: str) -> None:
        """Handle 429 rate limit error"""
        self._increase_backoff(endpoint)
    
    def get_stats(self, endpoint: Optional[str] = None) -> Dict:
        """
        Get rate limiting statistics.
        
        Args:
            endpoint: Specific endpoint (None for all)
            
        Returns:
            Statistics dictionary
        """
        if endpoint:
            endpoints = [endpoint]
        else:
            endpoints = list(self.call_history.keys())
        
        stats = {}
        for ep in endpoints:
            self._clean_old_calls(ep)
            call_count = len(self.call_history[ep])
            backoff_time = self._get_backoff_time(ep)
            
            stats[ep] = {
                'calls_in_window': call_count,
                'max_calls': self.max_calls,
                'backoff_remaining': backoff_time,
                'utilization': (call_count / self.max_calls) * 100 if self.max_calls > 0 else 0
            }
        
        return stats


class RetryWithBackoff:
    """Retry decorator with exponential backoff"""
    
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        max_backoff: float = 60.0,
        exceptions: tuple = (Exception,)
    ):
        """
        Initialize retry handler.
        
        Args:
            max_retries: Maximum number of retries
            backoff_factor: Multiplier for backoff time
            max_backoff: Maximum backoff time in seconds
            exceptions: Tuple of exceptions to catch
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.exceptions = exceptions
    
    def __call__(self, func):
        """Decorator implementation"""
        def wrapper(*args, **kwargs):
            backoff_time = 1.0
            
            for attempt in range(self.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except self.exceptions as e:
                    if attempt == self.max_retries:
                        logger.error(f"Max retries ({self.max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {backoff_time:.2f}s..."
                    )
                    time.sleep(backoff_time)
                    backoff_time = min(backoff_time * self.backoff_factor, self.max_backoff)
            
            return None
        
        return wrapper

