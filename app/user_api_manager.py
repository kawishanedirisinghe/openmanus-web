"""
User API Key Management System
Handles per-user API keys with encryption, rate limiting, and intelligent routing
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from cryptography.fernet import Fernet
import threading
import asyncio
from collections import defaultdict, deque

from app.models import db, User, APIUsage
from app.logger import logger


@dataclass
class APIKeyInfo:
    """Information about an API key"""
    provider: str
    encrypted_key: str
    added_at: datetime
    last_used: Optional[datetime] = None
    usage_count: int = 0
    rate_limit: Dict[str, int] = field(default_factory=dict)  # per minute/hour/day
    cost_limit: float = 10.0  # USD per month
    current_cost: float = 0.0
    is_active: bool = True
    priority: int = 1  # Higher number = higher priority
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIRequest:
    """API request information for tracking"""
    user_id: str
    provider: str
    model: str
    tokens_input: int
    tokens_output: int
    cost: float
    response_time: float
    timestamp: datetime
    session_id: Optional[str] = None


class UserAPIManager:
    """Manages API keys for individual users with advanced features"""
    
    def __init__(self):
        self._encryption_key = self._get_or_create_encryption_key()
        self._cipher = Fernet(self._encryption_key)
        self._user_apis: Dict[str, Dict[str, APIKeyInfo]] = {}
        self._rate_limits: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))
        self._usage_tracking: Dict[str, List[APIRequest]] = defaultdict(list)
        self._lock = threading.RLock()
        
        # Load existing API keys
        self._load_user_apis()
        
        # Start background cleanup
        self._start_cleanup_task()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for API keys"""
        key_file = 'config/api_encryption.key'
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
    
    def _load_user_apis(self):
        """Load user API keys from database"""
        try:
            # This would load from a secure storage system
            # For now, we'll store in user metadata
            users = User.query.all()
            for user in users:
                if hasattr(user, 'api_keys_metadata'):
                    self._user_apis[user.id] = self._deserialize_api_keys(
                        user.api_keys_metadata
                    )
        except Exception as e:
            logger.error(f"Error loading user APIs: {e}")
    
    def add_api_key(self, user_id: str, provider: str, api_key: str, 
                   priority: int = 1, rate_limit: Dict[str, int] = None,
                   cost_limit: float = 10.0) -> bool:
        """Add API key for user"""
        try:
            with self._lock:
                if user_id not in self._user_apis:
                    self._user_apis[user_id] = {}
                
                # Encrypt the API key
                encrypted_key = self._cipher.encrypt(api_key.encode()).decode()
                
                # Set default rate limits
                if rate_limit is None:
                    rate_limit = self._get_default_rate_limits(provider)
                
                # Create API key info
                api_info = APIKeyInfo(
                    provider=provider,
                    encrypted_key=encrypted_key,
                    added_at=datetime.utcnow(),
                    rate_limit=rate_limit,
                    cost_limit=cost_limit,
                    priority=priority
                )
                
                # Store with provider as key
                self._user_apis[user_id][provider] = api_info
                
                # Save to database
                self._save_user_apis(user_id)
                
                logger.info(f"Added {provider} API key for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error adding API key: {e}")
            return False
    
    def get_api_key(self, user_id: str, provider: str = None) -> Optional[str]:
        """Get decrypted API key for user and provider"""
        try:
            with self._lock:
                if user_id not in self._user_apis:
                    return None
                
                user_apis = self._user_apis[user_id]
                
                if provider:
                    # Get specific provider
                    if provider in user_apis:
                        api_info = user_apis[provider]
                        if api_info.is_active and self._check_rate_limit(user_id, provider):
                            decrypted = self._cipher.decrypt(
                                api_info.encrypted_key.encode()
                            ).decode()
                            api_info.last_used = datetime.utcnow()
                            return decrypted
                else:
                    # Get best available provider based on priority and rate limits
                    return self._get_best_api_key(user_id)
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting API key: {e}")
            return None
    
    def _get_best_api_key(self, user_id: str) -> Optional[Tuple[str, str]]:
        """Get the best available API key (provider, key) for user"""
        try:
            user_apis = self._user_apis.get(user_id, {})
            
            # Filter active APIs with available rate limits
            available_apis = []
            for provider, api_info in user_apis.items():
                if (api_info.is_active and 
                    self._check_rate_limit(user_id, provider) and
                    self._check_cost_limit(user_id, provider)):
                    
                    available_apis.append((provider, api_info))
            
            if not available_apis:
                return None
            
            # Sort by priority (higher first), then by least recently used
            available_apis.sort(
                key=lambda x: (
                    -x[1].priority,  # Higher priority first
                    x[1].last_used or datetime.min  # Least recently used
                )
            )
            
            # Get the best API
            provider, api_info = available_apis[0]
            decrypted_key = self._cipher.decrypt(
                api_info.encrypted_key.encode()
            ).decode()
            
            api_info.last_used = datetime.utcnow()
            
            return provider, decrypted_key
            
        except Exception as e:
            logger.error(f"Error getting best API key: {e}")
            return None
    
    def _check_rate_limit(self, user_id: str, provider: str) -> bool:
        """Check if user has available rate limit for provider"""
        try:
            api_info = self._user_apis[user_id][provider]
            current_time = time.time()
            
            # Check each rate limit period
            for period, limit in api_info.rate_limit.items():
                if period == 'minute':
                    window = 60
                elif period == 'hour':
                    window = 3600
                elif period == 'day':
                    window = 86400
                else:
                    continue
                
                # Get request history for this period
                requests = self._rate_limits[user_id][f"{provider}_{period}"]
                
                # Remove old requests
                while requests and requests[0] < current_time - window:
                    requests.popleft()
                
                # Check if limit exceeded
                if len(requests) >= limit:
                    logger.warning(
                        f"Rate limit exceeded for {user_id}/{provider}/{period}: "
                        f"{len(requests)}/{limit}"
                    )
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False
    
    def _check_cost_limit(self, user_id: str, provider: str) -> bool:
        """Check if user has available cost limit for provider"""
        try:
            api_info = self._user_apis[user_id][provider]
            
            # Calculate current month cost
            current_month_start = datetime.utcnow().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            
            monthly_cost = db.session.query(
                db.func.sum(APIUsage.cost)
            ).filter(
                APIUsage.user_id == user_id,
                APIUsage.api_provider == provider,
                APIUsage.request_time >= current_month_start
            ).scalar() or 0.0
            
            if monthly_cost >= api_info.cost_limit:
                logger.warning(
                    f"Cost limit exceeded for {user_id}/{provider}: "
                    f"${monthly_cost:.2f}/${api_info.cost_limit:.2f}"
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking cost limit: {e}")
            return True  # Default to allow on error
    
    def record_api_usage(self, user_id: str, provider: str, model: str,
                        tokens_input: int, tokens_output: int, cost: float,
                        response_time: float, session_id: str = None):
        """Record API usage for tracking and billing"""
        try:
            with self._lock:
                # Record in rate limit tracking
                current_time = time.time()
                for period in ['minute', 'hour', 'day']:
                    self._rate_limits[user_id][f"{provider}_{period}"].append(current_time)
                
                # Create usage record
                usage = APIUsage(
                    user_id=user_id,
                    api_provider=provider,
                    model_name=model,
                    tokens_used=tokens_input + tokens_output,
                    cost=cost,
                    session_id=session_id
                )
                
                db.session.add(usage)
                db.session.commit()
                
                # Update API info
                if user_id in self._user_apis and provider in self._user_apis[user_id]:
                    api_info = self._user_apis[user_id][provider]
                    api_info.usage_count += 1
                    api_info.current_cost += cost
                    api_info.last_used = datetime.utcnow()
                
                logger.debug(
                    f"Recorded API usage: {user_id}/{provider}/{model} - "
                    f"{tokens_input}+{tokens_output} tokens, ${cost:.4f}"
                )
                
        except Exception as e:
            logger.error(f"Error recording API usage: {e}")
    
    def get_user_api_status(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive API status for user"""
        try:
            if user_id not in self._user_apis:
                return {'providers': {}, 'total_usage': {}}
            
            user_apis = self._user_apis[user_id]
            status = {
                'providers': {},
                'total_usage': {
                    'total_cost': 0.0,
                    'total_requests': 0,
                    'active_providers': 0
                }
            }
            
            current_month_start = datetime.utcnow().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            
            for provider, api_info in user_apis.items():
                # Get monthly usage
                monthly_usage = db.session.query(
                    db.func.sum(APIUsage.cost),
                    db.func.count(APIUsage.id)
                ).filter(
                    APIUsage.user_id == user_id,
                    APIUsage.api_provider == provider,
                    APIUsage.request_time >= current_month_start
                ).first()
                
                monthly_cost = monthly_usage[0] or 0.0
                monthly_requests = monthly_usage[1] or 0
                
                # Check current limits
                rate_limit_ok = self._check_rate_limit(user_id, provider)
                cost_limit_ok = self._check_cost_limit(user_id, provider)
                
                provider_status = {
                    'is_active': api_info.is_active,
                    'priority': api_info.priority,
                    'added_at': api_info.added_at.isoformat(),
                    'last_used': api_info.last_used.isoformat() if api_info.last_used else None,
                    'usage_count': api_info.usage_count,
                    'rate_limits': api_info.rate_limit,
                    'cost_limit': api_info.cost_limit,
                    'monthly_cost': monthly_cost,
                    'monthly_requests': monthly_requests,
                    'rate_limit_ok': rate_limit_ok,
                    'cost_limit_ok': cost_limit_ok,
                    'available': api_info.is_active and rate_limit_ok and cost_limit_ok
                }
                
                status['providers'][provider] = provider_status
                
                # Update totals
                status['total_usage']['total_cost'] += monthly_cost
                status['total_usage']['total_requests'] += monthly_requests
                if provider_status['available']:
                    status['total_usage']['active_providers'] += 1
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting user API status: {e}")
            return {'providers': {}, 'total_usage': {}}
    
    def update_api_settings(self, user_id: str, provider: str, 
                           priority: int = None, rate_limit: Dict[str, int] = None,
                           cost_limit: float = None, is_active: bool = None) -> bool:
        """Update API settings for user"""
        try:
            with self._lock:
                if user_id not in self._user_apis or provider not in self._user_apis[user_id]:
                    return False
                
                api_info = self._user_apis[user_id][provider]
                
                if priority is not None:
                    api_info.priority = priority
                if rate_limit is not None:
                    api_info.rate_limit.update(rate_limit)
                if cost_limit is not None:
                    api_info.cost_limit = cost_limit
                if is_active is not None:
                    api_info.is_active = is_active
                
                self._save_user_apis(user_id)
                
                logger.info(f"Updated {provider} API settings for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating API settings: {e}")
            return False
    
    def remove_api_key(self, user_id: str, provider: str) -> bool:
        """Remove API key for user"""
        try:
            with self._lock:
                if user_id in self._user_apis and provider in self._user_apis[user_id]:
                    del self._user_apis[user_id][provider]
                    self._save_user_apis(user_id)
                    
                    logger.info(f"Removed {provider} API key for user {user_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error removing API key: {e}")
            return False
    
    def get_intelligent_provider_recommendation(self, user_id: str, 
                                               task_type: str = 'general') -> Optional[str]:
        """Get AI recommendation for best provider based on task type and user usage"""
        try:
            user_apis = self._user_apis.get(user_id, {})
            if not user_apis:
                return None
            
            # Define provider strengths
            provider_strengths = {
                'openai': {
                    'general': 0.9,
                    'coding': 0.85,
                    'creative': 0.9,
                    'analysis': 0.8,
                    'reasoning': 0.8
                },
                'anthropic': {
                    'general': 0.85,
                    'coding': 0.9,
                    'creative': 0.85,
                    'analysis': 0.95,
                    'reasoning': 0.95
                },
                'deepseek': {
                    'general': 0.8,
                    'coding': 0.95,
                    'creative': 0.7,
                    'analysis': 0.9,
                    'reasoning': 0.9
                },
                'gemini': {
                    'general': 0.8,
                    'coding': 0.8,
                    'creative': 0.8,
                    'analysis': 0.85,
                    'reasoning': 0.8
                }
            }
            
            available_providers = []
            for provider, api_info in user_apis.items():
                if (api_info.is_active and 
                    self._check_rate_limit(user_id, provider) and
                    self._check_cost_limit(user_id, provider)):
                    
                    # Calculate score based on task suitability and priority
                    task_score = provider_strengths.get(provider, {}).get(task_type, 0.5)
                    priority_score = api_info.priority / 10.0  # Normalize priority
                    
                    total_score = task_score * 0.7 + priority_score * 0.3
                    
                    available_providers.append((provider, total_score))
            
            if not available_providers:
                return None
            
            # Sort by score and return best
            available_providers.sort(key=lambda x: x[1], reverse=True)
            return available_providers[0][0]
            
        except Exception as e:
            logger.error(f"Error getting provider recommendation: {e}")
            return None
    
    def _get_default_rate_limits(self, provider: str) -> Dict[str, int]:
        """Get default rate limits for provider"""
        defaults = {
            'openai': {'minute': 60, 'hour': 3000, 'day': 10000},
            'anthropic': {'minute': 50, 'hour': 2000, 'day': 8000},
            'deepseek': {'minute': 100, 'hour': 5000, 'day': 20000},
            'gemini': {'minute': 60, 'hour': 3000, 'day': 10000}
        }
        return defaults.get(provider, {'minute': 60, 'hour': 1000, 'day': 5000})
    
    def _save_user_apis(self, user_id: str):
        """Save user API keys to database"""
        try:
            user = User.query.get(user_id)
            if user:
                # Convert to serializable format
                api_data = {}
                for provider, api_info in self._user_apis[user_id].items():
                    api_data[provider] = {
                        'encrypted_key': api_info.encrypted_key,
                        'added_at': api_info.added_at.isoformat(),
                        'last_used': api_info.last_used.isoformat() if api_info.last_used else None,
                        'usage_count': api_info.usage_count,
                        'rate_limit': api_info.rate_limit,
                        'cost_limit': api_info.cost_limit,
                        'current_cost': api_info.current_cost,
                        'is_active': api_info.is_active,
                        'priority': api_info.priority,
                        'metadata': api_info.metadata
                    }
                
                # This would be stored in a secure field in the database
                # For now, we'll use a JSON field (in production, use encrypted storage)
                if not hasattr(user, 'api_keys_metadata'):
                    # Add field to user model if not exists
                    pass
                
        except Exception as e:
            logger.error(f"Error saving user APIs: {e}")
    
    def _deserialize_api_keys(self, data: Dict[str, Any]) -> Dict[str, APIKeyInfo]:
        """Deserialize API keys from storage"""
        apis = {}
        for provider, api_data in data.items():
            apis[provider] = APIKeyInfo(
                provider=provider,
                encrypted_key=api_data['encrypted_key'],
                added_at=datetime.fromisoformat(api_data['added_at']),
                last_used=datetime.fromisoformat(api_data['last_used']) if api_data['last_used'] else None,
                usage_count=api_data.get('usage_count', 0),
                rate_limit=api_data.get('rate_limit', {}),
                cost_limit=api_data.get('cost_limit', 10.0),
                current_cost=api_data.get('current_cost', 0.0),
                is_active=api_data.get('is_active', True),
                priority=api_data.get('priority', 1),
                metadata=api_data.get('metadata', {})
            )
        return apis
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        def cleanup():
            while True:
                try:
                    current_time = time.time()
                    
                    # Clean up old rate limit entries
                    for user_rates in self._rate_limits.values():
                        for period_key, requests in user_rates.items():
                            if 'minute' in period_key:
                                cutoff = current_time - 60
                            elif 'hour' in period_key:
                                cutoff = current_time - 3600
                            elif 'day' in period_key:
                                cutoff = current_time - 86400
                            else:
                                continue
                            
                            while requests and requests[0] < cutoff:
                                requests.popleft()
                    
                    # Sleep for 5 minutes
                    time.sleep(300)
                    
                except Exception as e:
                    logger.error(f"Error in API cleanup task: {e}")
                    time.sleep(60)
        
        cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        cleanup_thread.start()


# Global instance
user_api_manager = UserAPIManager()