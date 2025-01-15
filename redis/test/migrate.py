import redis


def copy_data():
    source_redis = redis.Redis(host="localhost", port=6379, decode_responses=True)
    target_redis = redis.Redis(host="localhost", port=6380, decode_responses=True)

    for key in source_redis.keys("*"):
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

    print("Data copied from source to target Redis!")


if __name__ == "__main__":
    copy_data()
