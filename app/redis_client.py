import redis
import os
from dotenv import load_dotenv 
load_dotenv()
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "REDIS_HOST"),  # your Redis host
    port=int(os.getenv("REDIS_PORT", "REDIS_PORT")),  # your Redis port
    db=int(os.getenv("REDIS_DB", "REDIS_DB")),  # your Redis database number
    password=os.getenv("REDIS_PASSWORD", "REDIS_PASSWORD"),  # your Redis password
    decode_responses=True  # store strings instead of bytes
)

print(redis_client.ping())  # should print True