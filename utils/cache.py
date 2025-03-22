#!/usr/bin/env python3
"""
Caching utilities for SimpleAnthropicCLI
"""

import os
import time
import pickle
import logging
from typing import Dict, Any, Optional, Callable, Tuple

# Cache file path
CONFIG_DIR = os.path.expanduser("~/.simple_anthropic_cli")
CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
CACHE_EXPIRY = 3600  # Default cache expiry in seconds (1 hour)

class Cache:
    """Simple file-based cache implementation."""
    
    def __init__(self, cache_name: str, expiry: int = CACHE_EXPIRY):
        """Initialize cache.
        
        Args:
            cache_name: Name for the cache file
            expiry: Cache expiry time in seconds
        """
        self.cache_name = cache_name
        self.expiry = expiry
        self.cache_file = os.path.join(CACHE_DIR, f"{cache_name}.cache")
        self.cache = self._load_cache()
        
        # Ensure the cache directory exists
        os.makedirs(CACHE_DIR, exist_ok=True)
    
    def _load_cache(self) -> Dict[str, Tuple[Any, float]]:
        """Load cache from file.
        
        Returns:
            Dictionary of cached items
        """
        if not os.path.exists(self.cache_file):
            return {}
            
        try:
            with open(self.cache_file, 'rb') as f:
                cache = pickle.load(f)
            
            # Check for expired entries and clean them
            now = time.time()
            expired_keys = [k for k, (_, timestamp) in cache.items() 
                           if now - timestamp > self.expiry]
            
            # Remove expired entries
            for k in expired_keys:
                del cache[k]
                
            return cache
        except Exception as e:
            logging.error(f"Error loading cache {self.cache_name}: {e}")
            return {}
    
    def _save_cache(self) -> bool:
        """Save cache to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            return True
        except Exception as e:
            logging.error(f"Error saving cache {self.cache_name}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        if key not in self.cache:
            return None
            
        value, timestamp = self.cache[key]
        
        # Check if expired
        if time.time() - timestamp > self.expiry:
            del self.cache[key]
            self._save_cache()
            return None
            
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            
        Returns:
            True if successful, False otherwise
        """
        self.cache[key] = (value, time.time())
        return self._save_cache()
    
    def delete(self, key: str) -> bool:
        """Delete a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        if key in self.cache:
            del self.cache[key]
            return self._save_cache()
        return True
    
    def clear(self) -> bool:
        """Clear all cache entries.
        
        Returns:
            True if successful, False otherwise
        """
        self.cache = {}
        return self._save_cache()
    
    def cached(self, func: Callable):
        """Decorator for caching function results.
        
        Args:
            func: Function to cache
            
        Returns:
            Decorated function
        """
        def wrapper(*args, **kwargs):
            # Create a key from the function name and arguments
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check cache
            cached_value = self.get(key)
            if cached_value is not None:
                logging.debug(f"Cache hit for {key}")
                return cached_value
                
            # Cache miss, call the function
            result = func(*args, **kwargs)
            
            # Cache the result
            self.set(key, result)
            
            return result
        
        return wrapper
    
    @staticmethod
    def clear_all_caches() -> None:
        """Clear all caches."""
        if not os.path.exists(CACHE_DIR):
            return
            
        for filename in os.listdir(CACHE_DIR):
            if filename.endswith('.cache'):
                try:
                    os.remove(os.path.join(CACHE_DIR, filename))
                except Exception as e:
                    logging.error(f"Error removing cache file {filename}: {e}")