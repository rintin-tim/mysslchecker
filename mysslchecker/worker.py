import os

import redis
from rq import Worker, Queue, Connection
# from redis import Redis

listen = ['high', 'default', 'low']

local_url = "redis-11259.c9.us-east-1-2.ec2.cloud.redislabs.com"
local_port = 11259
local_password = "oG1WgPlsc81oXKANqLCrr8LZRnqgKXyB"

# redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
redis_url = os.getenv('REDISTOGO_URL', local_url)

# conn = redis.from_url(redis_url, )
if 'REDISTOGO_URL' in os.environ:
    print("returning os environment conn")
    conn = redis.from_url(redis_url)
else:
    print("returning no environment conn")
    conn = redis.Redis(host=local_url, port=local_port, password=local_password)


if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        print("about to run worker")
        worker.work()
        print("running worker")
    # response = program.result
