import json
from functools import wraps
import redis
from extensions import redis_client

DEFAULT_TTL = 300


def cache_get(key):
    try:
        data = redis_client.get(key)
        return json.loads(data) if data else None
    except (redis.RedisError, json.JSONDecodeError, ConnectionError, OSError):
        return None


def cache_set(key, value, ttl=DEFAULT_TTL):
    try:
        redis_client.setex(key, ttl, json.dumps(value, default=str))
    except (redis.RedisError, ConnectionError, OSError):
        pass


def cache_delete(*keys):
    try:
        if keys:
            redis_client.delete(*keys)
    except (redis.RedisError, ConnectionError, OSError):
        pass


def invalidate_dashboard_cache():
    cache_delete('admin:stats', 'student:drives', 'admin:companies', 'admin:drives', 'admin:students')


def cached(key_prefix, ttl=DEFAULT_TTL):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            cache_key = f'{key_prefix}'
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                return cached_value
            result = fn(*args, **kwargs)
            cache_set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
