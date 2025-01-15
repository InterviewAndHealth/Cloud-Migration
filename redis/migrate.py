import os
import pathlib

import dotenv

import redis

path = pathlib.Path(__file__).parent.absolute() / ".env"
dotenv.load_dotenv(dotenv_path=path, override=True)

HOST_SOURCE = os.getenv("HOST_SOURCE")
PORT_SOURCE = os.getenv("PORT_SOURCE")
PASSWORD_SOURCE = os.getenv("PASSWORD_SOURCE")

HOST_DEST = os.getenv("HOST_DEST")
PORT_DEST = os.getenv("PORT_DEST")
PASSWORD_DEST = os.getenv("PASSWORD_DEST")

DB = int(os.getenv("DB", "0"))


def create_redis_connection(host, port, password, db):
    """Create and return a Redis connection."""
    return redis.Redis(
        host=host,
        port=port,
        password=password,
        db=db,
        decode_responses=True,
    )


def migrate_key(source_redis, target_redis, key):
    """Migrate a single key based on its Redis data type."""
    data_type = source_redis.type(key)
    if data_type == "string":
        target_redis.set(key, source_redis.get(key))
    elif data_type == "hash":
        target_redis.hmset(key, source_redis.hgetall(key))
    elif data_type == "list":
        items = source_redis.lrange(key, 0, -1)
        for item in reversed(items):
            target_redis.lpush(key, item)

    # Transfer TTL
    ttl = source_redis.ttl(key)
    if ttl > 0:
        target_redis.expire(key, ttl)


def migrate_data():
    """Migrate data from source Redis to target Redis."""
    print("INFO: Connecting to source Redis")
    source_redis = create_redis_connection(
        HOST_SOURCE, PORT_SOURCE, PASSWORD_SOURCE, DB
    )
    print("INFO: Connecting to target Redis")
    target_redis = create_redis_connection(HOST_DEST, PORT_DEST, PASSWORD_DEST, DB)

    keys = source_redis.keys("*")
    if not keys:
        print("INFO: No keys found in the source Redis!")
        return

    print(f"INFO: Found {len(keys)} keys in the source Redis. Migrating data...")
    for key in keys:
        migrate_key(source_redis, target_redis, key)
    print("INFO: Data copied from source to target Redis!")


if __name__ == "__main__":
    migrate_data()
