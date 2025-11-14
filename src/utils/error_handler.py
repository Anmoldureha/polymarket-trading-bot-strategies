"""Enhanced error handling with graceful degradation"""

import time
from typing import Dict, Optional, Callable, Any, Type
from functools import wraps
from ..utils.logger import setup_logger


logger = setup_logger(__name__)


class ErrorHandler:
    """Centralized error handling with graceful degradation"""
    
    def __init__(self):
        """Initialize error handler"""
        self.error_stats = {
            'total_errors': 0,
            'errors_by_type': {},
            'recent_errors': []
        }
    
    def handle_error(
        self,
        error: Exception,
        context: str = "",
        fallback_value: Any = None,
        retry: bool = False,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Any:
        """
        Handle an error with graceful degradation.
        
        Args:
            error: Exception that occurred
            context: Context where error occurred
            fallback_value: Value to return if error persists
            retry: Whether to retry
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries
            
        Returns:
            Fallback value or None
        """
        error_type = type(error).__name__
        self.error_stats['total_errors'] += 1
        self.error_stats['errors_by_type'][error_type] = \
            self.error_stats['errors_by_type'].get(error_type, 0) + 1
        
        # Record recent error
        self.error_stats['recent_errors'].append({
            'type': error_type,
            'message': str(error),
            'context': context,
            'timestamp': time.time()
        })
        
        # Keep only last 100 errors
        if len(self.error_stats['recent_errors']) > 100:
            self.error_stats['recent_errors'] = self.error_stats['recent_errors'][-100:]
        
        # Log error
        logger.error(f"Error in {context}: {error_type} - {str(error)}")
        
        # Retry if requested
        if retry and max_retries > 0:
            logger.info(f"Retrying {context} (attempts remaining: {max_retries})")
            time.sleep(retry_delay)
            return self.handle_error(
                error, context, fallback_value, retry=True,
                max_retries=max_retries - 1, retry_delay=retry_delay * 2
            )
        
        # Return fallback value
        if fallback_value is not None:
            logger.debug(f"Using fallback value for {context}")
            return fallback_value
        
        return None
    
    def get_user_friendly_message(self, error: Exception) -> str:
        """
        Get user-friendly error message.
        
        Args:
            error: Exception
            
        Returns:
            User-friendly message
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        # Common error mappings
        friendly_messages = {
            'ConnectionError': 'Unable to connect to Polymarket. Please check your internet connection.',
            'Timeout': 'Request timed out. The API may be slow or unavailable.',
            'HTTPError': f'API returned an error: {error_msg}',
            'RateLimitError': 'Rate limit exceeded. Please wait a moment and try again.',
            'ValueError': f'Invalid data: {error_msg}',
            'KeyError': f'Missing required data: {error_msg}',
        }
        
        # Check for specific error types
        if '429' in error_msg or 'rate limit' in error_msg.lower():
            return friendly_messages.get('RateLimitError', 'Rate limit exceeded.')
        
        if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
            return friendly_messages.get('Timeout', 'Request timed out.')
        
        if 'connection' in error_msg.lower():
            return friendly_messages.get('ConnectionError', 'Connection error.')
        
        # Return mapped message or generic
        return friendly_messages.get(error_type, f'An error occurred: {error_msg}')
    
    def get_stats(self) -> Dict:
        """Get error statistics"""
        return {
            **self.error_stats,
            'error_rate': (
                self.error_stats['total_errors'] / max(1, len(self.error_stats['recent_errors']))
                if self.error_stats['recent_errors'] else 0
            )
        }


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    fallback_value: Any = None
):
    """
    Decorator for retrying functions on error.
    
    Args:
        max_retries: Maximum retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch
        fallback_value: Value to return if all retries fail
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.2f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Max retries exceeded for {func.__name__}: {e}")
            
            # All retries failed
            if fallback_value is not None:
                logger.debug(f"Using fallback value for {func.__name__}")
                return fallback_value
            
            raise last_exception
        
        return wrapper
    return decorator


def graceful_degradation(fallback_value: Any = None, exceptions: tuple = (Exception,)):
    """
    Decorator for graceful degradation on error.
    
    Args:
        fallback_value: Value to return on error
        exceptions: Tuple of exceptions to catch
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                logger.error(f"Error in {func.__name__}: {e}")
                if fallback_value is not None:
                    return fallback_value
                return None
        
        return wrapper
    return decorator

