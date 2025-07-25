# Multi-API Key Configuration Guide

This guide explains how to configure and use multiple API keys with automatic rate limiting and key rotation in OpenManus.

## Overview

The multi-API key system provides:

- **Multiple API Keys**: Configure multiple API keys for the same LLM provider
- **Rate Limiting**: Set individual rate limits for each API key (per minute/hour/day)
- **Automatic Rotation**: Automatically switch to backup keys when rate limits are hit
- **Priority System**: Define priority order for key usage
- **Failure Handling**: Temporary key disabling after consecutive failures
- **Usage Tracking**: Monitor usage statistics for each key

## Configuration

### Basic Multi-Key Setup

Add multiple API keys to your `config.toml` file:

```toml
[llm]
model = "claude-3-7-sonnet-20250219"
base_url = "https://api.anthropic.com/v1/"
api_key = "YOUR_API_KEY"  # Legacy single key (optional)
max_tokens = 8192
temperature = 0.0

# Multi-API key configuration
[[llm.api_keys]]
api_key = "YOUR_PRIMARY_API_KEY"
name = "Primary Key"
max_requests_per_minute = 60
max_requests_per_hour = 3600
max_requests_per_day = 86400
priority = 1
enabled = true

[[llm.api_keys]]
api_key = "YOUR_SECONDARY_API_KEY"
name = "Secondary Key"
max_requests_per_minute = 30
max_requests_per_hour = 1800
max_requests_per_day = 43200
priority = 2
enabled = true

[[llm.api_keys]]
api_key = "YOUR_BACKUP_API_KEY"
name = "Backup Key"
max_requests_per_minute = 20
max_requests_per_hour = 1200
max_requests_per_day = 28800
priority = 3
enabled = true
```

### Vision Model Configuration

Configure multiple keys for vision models:

```toml
[llm.vision]
model = "claude-3-7-sonnet-20250219"
base_url = "https://api.anthropic.com/v1/"
max_tokens = 8192
temperature = 0.0

[[llm.vision.api_keys]]
api_key = "YOUR_VISION_PRIMARY_KEY"
name = "Vision Primary"
max_requests_per_minute = 30  # Vision models often have lower limits
max_requests_per_hour = 1800
max_requests_per_day = 43200
priority = 1
enabled = true

[[llm.vision.api_keys]]
api_key = "YOUR_VISION_SECONDARY_KEY"
name = "Vision Secondary"
max_requests_per_minute = 15
max_requests_per_hour = 900
max_requests_per_day = 21600
priority = 2
enabled = true
```

## API Key Settings

Each API key supports the following configuration options:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `api_key` | string | required | The actual API key |
| `name` | string | optional | Human-readable name for the key |
| `max_requests_per_minute` | integer | 60 | Maximum requests per minute |
| `max_requests_per_hour` | integer | 3600 | Maximum requests per hour |
| `max_requests_per_day` | integer | 86400 | Maximum requests per day |
| `priority` | integer | 1 | Priority order (lower = higher priority) |
| `enabled` | boolean | true | Whether the key is active |

## Usage Examples

### Basic Usage with Wrapper

```python
from app.config import Config
from app.llm_client_wrapper import create_llm_wrapper
import openai

# Create client factory
def create_openai_client(api_key: str):
    return openai.OpenAI(api_key=api_key)

# Get configuration
config = Config()
llm_settings = config.llm.get("default")

# Create wrapper
llm_wrapper = create_llm_wrapper(llm_settings, create_openai_client)

# Define request function
def make_chat_request(client, messages, **kwargs):
    return client.chat.completions.create(
        model=llm_settings.model,
        messages=messages,
        max_tokens=llm_settings.max_tokens,
        temperature=llm_settings.temperature,
        **kwargs
    )

# Make request with automatic key rotation
try:
    messages = [{"role": "user", "content": "Hello!"}]
    response = llm_wrapper.make_request(make_chat_request, messages)
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Request failed: {e}")
```

### Monitoring Usage

```python
# Get usage statistics
stats = llm_wrapper.get_usage_stats()
for key_name, key_stats in stats.items():
    print(f"{key_name}:")
    print(f"  Requests this minute: {key_stats['requests_this_minute']}")
    print(f"  Requests this hour: {key_stats['requests_this_hour']}")
    print(f"  Consecutive failures: {key_stats['consecutive_failures']}")
    print(f"  Is rate limited: {key_stats['is_rate_limited']}")

# Get current active key
current_key = llm_wrapper.get_current_key_info()
print(f"Currently using: {current_key}")
```

## How It Works

### Key Selection Algorithm

1. **Filter enabled keys**: Only consider keys where `enabled = true`
2. **Sort by priority**: Lower priority numbers are selected first
3. **Check rate limits**: Skip keys that have exceeded their limits
4. **Check failure status**: Skip keys temporarily disabled due to failures
5. **Select best available**: Return the highest priority available key

### Rate Limit Handling

When a rate limit is detected:

1. **Mark key as rate limited**: The key is temporarily disabled
2. **Rotate to next key**: Automatically try the next available key
3. **Reset after cooldown**: Keys are re-enabled after rate limit periods expire

### Failure Handling

The system tracks failures and temporarily disables problematic keys:

- **3+ consecutive failures**: Key is disabled for 5 minutes
- **Authentication errors**: Immediate rotation to next key
- **Server errors**: Retry with exponential backoff

### Error Types Handled

| Error Type | Action | Retry Behavior |
|------------|--------|----------------|
| Rate Limit (429) | Rotate to next key | Immediate |
| Auth Error (401/403) | Rotate to next key | Immediate |
| Server Error (5xx) | Retry same key | Exponential backoff |
| Timeout | Retry same key | Exponential backoff |
| Other errors | Fail immediately | No retry |

## Best Practices

### Key Configuration

1. **Use different rate limits**: Configure realistic limits based on your API plans
2. **Set priorities wisely**: Put your highest-tier keys as priority 1
3. **Enable backup keys**: Always have at least 2-3 keys configured
4. **Monitor usage**: Regularly check usage statistics

### Rate Limit Settings

```toml
# Example: Different tiers
[[llm.api_keys]]
api_key = "premium_key"
name = "Premium Tier"
max_requests_per_minute = 100
max_requests_per_hour = 6000
priority = 1

[[llm.api_keys]]
api_key = "standard_key"
name = "Standard Tier"
max_requests_per_minute = 50
max_requests_per_hour = 3000
priority = 2

[[llm.api_keys]]
api_key = "free_key"
name = "Free Tier"
max_requests_per_minute = 10
max_requests_per_hour = 200
priority = 3
```

### Security Considerations

1. **Environment Variables**: Store API keys in environment variables
2. **Key Rotation**: Regularly rotate your API keys
3. **Monitoring**: Monitor for unusual usage patterns
4. **Access Control**: Limit access to configuration files

```bash
# Example environment setup
export PRIMARY_API_KEY="your_primary_key"
export SECONDARY_API_KEY="your_secondary_key"
export BACKUP_API_KEY="your_backup_key"
```

Then reference in config:

```toml
[[llm.api_keys]]
api_key = "${PRIMARY_API_KEY}"
name = "Primary Key"
# ... other settings
```

## Troubleshooting

### Common Issues

**No available keys error**
- Check that at least one key is enabled
- Verify rate limits aren't too restrictive
- Check for authentication errors in logs

**Frequent key rotation**
- Rate limits may be set too low
- Check API provider's actual limits
- Monitor usage patterns

**Authentication failures**
- Verify API keys are valid
- Check API key permissions
- Ensure correct API endpoints

### Debugging

Enable debug logging to see key rotation in action:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will show:
- Key selection decisions
- Rate limit hits
- Key rotations
- Usage tracking

### Monitoring Commands

```python
# Check current system status
from app.api_key_manager import api_key_manager

# Get all usage stats
for key in llm_settings.api_keys:
    stats = api_key_manager.get_usage_stats(key.api_key)
    print(f"{key.name}: {stats}")
```

## Migration from Single Key

If you're currently using a single API key, migration is seamless:

1. **Keep existing config**: Your single `api_key` will continue to work
2. **Add multi-key section**: Add `[[llm.api_keys]]` sections
3. **Test gradually**: The system will prefer multi-key config when available
4. **Remove single key**: Once confident, remove the single `api_key` line

The system maintains backward compatibility with single-key configurations.
