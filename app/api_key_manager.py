"""
API Key Manager with Rate Limiting and Automatic Rotation

This module provides functionality to manage multiple API keys with individual rate limits
and automatic rotation when keys hit their limits.
"""

import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

from .config import APIKeySettings

logger = logging.getLogger(__name__)


@dataclass
class KeyUsageTracker:
    """Tracks usage statistics for an API key"""
    requests_this_minute: deque = field(default_factory=deque)
    requests_this_hour: deque = field(default_factory=deque)
    requests_this_day: deque = field(default_factory=deque)
    last_used: Optional[datetime] = None
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    is_rate_limited: bool = False
    rate_limit_reset_time: Optional[datetime] = None


class APIKeyManager:
    """
    Manages multiple API keys with rate limiting and automatic rotation.
    
    Features:
    - Rate limiting per key (minute/hour/day)
    - Automatic key rotation when limits are hit
    - Priority-based key selection
    - Failure tracking and temporary key disabling
    - Thread-safe operations
    """
    
    def __init__(self):
        self._usage_trackers: Dict[str, KeyUsageTracker] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
        
    def register_keys(self, api_keys: List[APIKeySettings]) -> None:
        """Register API keys for management"""
        with self._lock:
            for key_config in api_keys:
                if key_config.enabled and key_config.api_key not in self._usage_trackers:
                    self._usage_trackers[key_config.api_key] = KeyUsageTracker()
                    logger.info(f"Registered API key: {key_config.name or 'Unnamed'}")
    
    def get_available_key(self, api_keys: List[APIKeySettings]) -> Optional[Tuple[str, APIKeySettings]]:
        """
        Get the next available API key based on rate limits and priority.
        
        Returns:
            Tuple of (api_key, key_config) or None if no keys available
        """
        with self._lock:
            self._cleanup_old_usage_data()
            
            # Sort keys by priority (lower number = higher priority)
            sorted_keys = sorted(
                [k for k in api_keys if k.enabled], 
                key=lambda x: (x.priority, x.api_key)
            )
            
            current_time = datetime.now()
            
            for key_config in sorted_keys:
                api_key = key_config.api_key
                
                # Initialize tracker if not exists
                if api_key not in self._usage_trackers:
                    self._usage_trackers[api_key] = KeyUsageTracker()
                
                tracker = self._usage_trackers[api_key]
                
                # Check if key is temporarily disabled due to failures
                if self._is_key_temporarily_disabled(tracker, current_time):
                    continue
                
                # Check if key is within rate limits
                if self._is_key_within_limits(key_config, tracker, current_time):
                    logger.debug(f"Selected API key: {key_config.name or 'Unnamed'}")
                    return api_key, key_config
                else:
                    logger.debug(f"API key {key_config.name or 'Unnamed'} is rate limited")
            
            logger.warning("No available API keys within rate limits")
            return None
    
    def record_request(self, api_key: str) -> None:
        """Record a successful API request"""
        with self._lock:
            if api_key not in self._usage_trackers:
                self._usage_trackers[api_key] = KeyUsageTracker()
            
            tracker = self._usage_trackers[api_key]
            current_time = datetime.now()
            
            # Add timestamp to all tracking queues
            tracker.requests_this_minute.append(current_time)
            tracker.requests_this_hour.append(current_time)
            tracker.requests_this_day.append(current_time)
            tracker.last_used = current_time
            
            # Reset failure counter on successful request
            tracker.consecutive_failures = 0
            tracker.is_rate_limited = False
            tracker.rate_limit_reset_time = None
            
            logger.debug(f"Recorded successful request for API key")
    
    def record_rate_limit_error(self, api_key: str, reset_time: Optional[datetime] = None) -> None:
        """Record a rate limit error for an API key"""
        with self._lock:
            if api_key not in self._usage_trackers:
                self._usage_trackers[api_key] = KeyUsageTracker()
            
            tracker = self._usage_trackers[api_key]
            tracker.is_rate_limited = True
            tracker.rate_limit_reset_time = reset_time or datetime.now() + timedelta(minutes=1)
            
            logger.warning(f"API key hit rate limit, disabled until {tracker.rate_limit_reset_time}")
    
    def record_failure(self, api_key: str, error_type: str = "unknown") -> None:
        """Record a failure for an API key"""
        with self._lock:
            if api_key not in self._usage_trackers:
                self._usage_trackers[api_key] = KeyUsageTracker()
            
            tracker = self._usage_trackers[api_key]
            tracker.consecutive_failures += 1
            tracker.last_failure_time = datetime.now()
            
            logger.warning(f"Recorded failure for API key: {error_type} (consecutive: {tracker.consecutive_failures})")
    
    def get_usage_stats(self, api_key: str) -> Dict:
        """Get usage statistics for an API key"""
        with self._lock:
            if api_key not in self._usage_trackers:
                return {}
            
            tracker = self._usage_trackers[api_key]
            current_time = datetime.now()
            
            # Clean old data for accurate counts
            self._clean_usage_queue(tracker.requests_this_minute, current_time, timedelta(minutes=1))
            self._clean_usage_queue(tracker.requests_this_hour, current_time, timedelta(hours=1))
            self._clean_usage_queue(tracker.requests_this_day, current_time, timedelta(days=1))
            
            return {
                "requests_this_minute": len(tracker.requests_this_minute),
                "requests_this_hour": len(tracker.requests_this_hour),
                "requests_this_day": len(tracker.requests_this_day),
                "last_used": tracker.last_used,
                "consecutive_failures": tracker.consecutive_failures,
                "is_rate_limited": tracker.is_rate_limited,
                "rate_limit_reset_time": tracker.rate_limit_reset_time
            }
    
    def _is_key_within_limits(self, key_config: APIKeySettings, tracker: KeyUsageTracker, current_time: datetime) -> bool:
        """Check if a key is within its rate limits"""
        # Check if manually marked as rate limited
        if tracker.is_rate_limited:
            if tracker.rate_limit_reset_time and current_time >= tracker.rate_limit_reset_time:
                tracker.is_rate_limited = False
                tracker.rate_limit_reset_time = None
            else:
                return False
        
        # Clean old usage data
        self._clean_usage_queue(tracker.requests_this_minute, current_time, timedelta(minutes=1))
        self._clean_usage_queue(tracker.requests_this_hour, current_time, timedelta(hours=1))
        self._clean_usage_queue(tracker.requests_this_day, current_time, timedelta(days=1))
        
        # Check rate limits
        if len(tracker.requests_this_minute) >= key_config.max_requests_per_minute:
            return False
        if len(tracker.requests_this_hour) >= key_config.max_requests_per_hour:
            return False
        if len(tracker.requests_this_day) >= key_config.max_requests_per_day:
            return False
        
        return True
    
    def _is_key_temporarily_disabled(self, tracker: KeyUsageTracker, current_time: datetime) -> bool:
        """Check if a key should be temporarily disabled due to failures"""
        # Disable key if too many consecutive failures
        if tracker.consecutive_failures >= 3:
            if tracker.last_failure_time:
                # Re-enable after 5 minutes
                if current_time - tracker.last_failure_time > timedelta(minutes=5):
                    tracker.consecutive_failures = 0
                    return False
                return True
        return False
    
    def _clean_usage_queue(self, usage_queue: deque, current_time: datetime, time_window: timedelta) -> None:
        """Remove old entries from usage queue"""
        cutoff_time = current_time - time_window
        while usage_queue and usage_queue[0] < cutoff_time:
            usage_queue.popleft()
    
    def _cleanup_old_usage_data(self) -> None:
        """Periodic cleanup of old usage data"""
        current_time_seconds = time.time()
        if current_time_seconds - self._last_cleanup < self._cleanup_interval:
            return
        
        current_time = datetime.now()
        for tracker in self._usage_trackers.values():
            self._clean_usage_queue(tracker.requests_this_minute, current_time, timedelta(minutes=1))
            self._clean_usage_queue(tracker.requests_this_hour, current_time, timedelta(hours=1))
            self._clean_usage_queue(tracker.requests_this_day, current_time, timedelta(days=1))
        
        self._last_cleanup = current_time_seconds


# Global instance
api_key_manager = APIKeyManager()
