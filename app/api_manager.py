import asyncio
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from threading import Lock
import logging

logger = logging.getLogger(__name__)


@dataclass
class APIKeyConfig:
    """Configuration for a single API key with rate limiting"""
    key: str
    name: str = ""
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 3600
    max_requests_per_day: int = 86400
    priority: int = 1  # Lower number = higher priority
    enabled: bool = True
    
    # Rate limiting tracking
    minute_requests: List[float] = field(default_factory=list)
    hour_requests: List[float] = field(default_factory=list)
    day_requests: List[float] = field(default_factory=list)
    
    # Lock for thread safety
    _lock: Lock = field(default_factory=Lock)
    
    def __post_init__(self):
        if not self.name:
            self.name = f"key_{self.key[:8]}..."
    
    def can_make_request(self) -> bool:
        """Check if this API key can make a request based on rate limits"""
        if not self.enabled:
            return False
            
        with self._lock:
            current_time = time.time()
            
            # Clean old requests
            self._clean_old_requests(current_time)
            
            # Check rate limits
            if len(self.minute_requests) >= self.max_requests_per_minute:
                return False
            if len(self.hour_requests) >= self.max_requests_per_hour:
                return False
            if len(self.day_requests) >= self.max_requests_per_day:
                return False
                
            return True
    
    def record_request(self) -> None:
        """Record a request for rate limiting purposes"""
        with self._lock:
            current_time = time.time()
            self.minute_requests.append(current_time)
            self.hour_requests.append(current_time)
            self.day_requests.append(current_time)
            
            # Clean old requests
            self._clean_old_requests(current_time)
    
    def _clean_old_requests(self, current_time: float) -> None:
        """Remove old requests from tracking lists"""
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        day_ago = current_time - 86400
        
        self.minute_requests = [t for t in self.minute_requests if t > minute_ago]
        self.hour_requests = [t for t in self.hour_requests if t > hour_ago]
        self.day_requests = [t for t in self.day_requests if t > day_ago]
    
    def get_next_available_time(self) -> Optional[float]:
        """Get the next time when this key will be available for requests"""
        if not self.enabled:
            return None
            
        with self._lock:
            current_time = time.time()
            self._clean_old_requests(current_time)
            
            next_times = []
            
            # Check minute limit
            if len(self.minute_requests) >= self.max_requests_per_minute:
                oldest_minute = min(self.minute_requests)
                next_times.append(oldest_minute + 60)
            
            # Check hour limit
            if len(self.hour_requests) >= self.max_requests_per_hour:
                oldest_hour = min(self.hour_requests)
                next_times.append(oldest_hour + 3600)
            
            # Check day limit
            if len(self.day_requests) >= self.max_requests_per_day:
                oldest_day = min(self.day_requests)
                next_times.append(oldest_day + 86400)
            
            return min(next_times) if next_times else current_time
    
    def get_rate_limit_status(self) -> Dict[str, int]:
        """Get current rate limit usage"""
        with self._lock:
            current_time = time.time()
            self._clean_old_requests(current_time)
            
            return {
                "minute_used": len(self.minute_requests),
                "minute_limit": self.max_requests_per_minute,
                "hour_used": len(self.hour_requests),
                "hour_limit": self.max_requests_per_hour,
                "day_used": len(self.day_requests),
                "day_limit": self.max_requests_per_day,
            }


class APIKeyManager:
    """Manages multiple API keys with automatic fallback and rate limiting"""
    
    def __init__(self, api_keys: List[APIKeyConfig]):
        self.api_keys = sorted(api_keys, key=lambda x: x.priority)
        self.current_key_index = 0
        self._lock = Lock()
    
    def get_available_key(self) -> Optional[APIKeyConfig]:
        """Get the next available API key that can make a request"""
        with self._lock:
            # First try the current key
            if (self.current_key_index < len(self.api_keys) and 
                self.api_keys[self.current_key_index].can_make_request()):
                return self.api_keys[self.current_key_index]
            
            # Try all keys starting from highest priority
            for i, key_config in enumerate(self.api_keys):
                if key_config.can_make_request():
                    self.current_key_index = i
                    return key_config
            
            return None
    
    def record_request(self, api_key: str) -> None:
        """Record a request for the given API key"""
        with self._lock:
            for key_config in self.api_keys:
                if key_config.key == api_key:
                    key_config.record_request()
                    break
    
    def mark_key_failed(self, api_key: str, temporary: bool = True) -> None:
        """Mark a key as failed (temporarily or permanently disable it)"""
        with self._lock:
            for key_config in self.api_keys:
                if key_config.key == api_key:
                    if not temporary:
                        key_config.enabled = False
                        logger.warning(f"API key {key_config.name} permanently disabled")
                    else:
                        logger.warning(f"API key {key_config.name} temporarily failed")
                    break
    
    def get_next_available_time(self) -> Optional[float]:
        """Get the next time when any key will be available"""
        next_times = []
        for key_config in self.api_keys:
            next_time = key_config.get_next_available_time()
            if next_time:
                next_times.append(next_time)
        
        return min(next_times) if next_times else None
    
    def get_all_keys_status(self) -> List[Dict]:
        """Get status of all API keys"""
        status_list = []
        for key_config in self.api_keys:
            status = {
                "name": key_config.name,
                "key_preview": f"{key_config.key[:8]}...",
                "priority": key_config.priority,
                "enabled": key_config.enabled,
                "can_make_request": key_config.can_make_request(),
                "rate_limits": key_config.get_rate_limit_status(),
            }
            next_time = key_config.get_next_available_time()
            if next_time and next_time > time.time():
                status["next_available_in"] = int(next_time - time.time())
            status_list.append(status)
        
        return status_list
    
    async def wait_for_available_key(self, max_wait_time: int = 300) -> Optional[APIKeyConfig]:
        """Wait for an available key with exponential backoff"""
        start_time = time.time()
        wait_time = 1
        
        while time.time() - start_time < max_wait_time:
            key = self.get_available_key()
            if key:
                return key
            
            # Wait with exponential backoff
            logger.info(f"No API keys available, waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            wait_time = min(wait_time * 2, 60)  # Cap at 60 seconds
        
        logger.error(f"No API keys became available within {max_wait_time} seconds")
        return None


def create_api_key_manager_from_config(keys_config: List[Dict]) -> APIKeyManager:
    """Create an APIKeyManager from configuration data"""
    api_keys = []
    
    for i, key_config in enumerate(keys_config):
        api_key = APIKeyConfig(
            key=key_config["api_key"],
            name=key_config.get("name", f"key_{i+1}"),
            max_requests_per_minute=key_config.get("max_requests_per_minute", 60),
            max_requests_per_hour=key_config.get("max_requests_per_hour", 3600),
            max_requests_per_day=key_config.get("max_requests_per_day", 86400),
            priority=key_config.get("priority", i + 1),
            enabled=key_config.get("enabled", True),
        )
        api_keys.append(api_key)
    
    return APIKeyManager(api_keys)
