import os
import redis

_REDIS_HOST = os.getenv("REDIS_HOST", "redis")
_REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
_REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None


def _redis_test():
    redis_cli = redis.Redis(
        host=_REDIS_HOST,
        port=_REDIS_PORT,
        password=_REDIS_PASSWORD,
        charset="utf-8",
        decode_responses=True,
    )
    connection = redis_cli.ping()
    print(connection)


def _get_redis_handler():
    return redis.Redis(
        host=_REDIS_HOST,
        port=_REDIS_PORT,
        password=_REDIS_PASSWORD,
        charset="utf-8",
        decode_responses=True,
    )

def write_key_to_redis(key: str, value: str):
    redis_handler = _get_redis_handler()
    redis_handler.set(key, value)
    redis_handler.save()


def get_value_from_redis(key: str):
    redis_handler = _get_redis_handler()
    value = redis_handler.get(key)
    if value is None:
        raise ValueError(f"Key {key} not found in Redis")
    return redis_handler.get(key)
