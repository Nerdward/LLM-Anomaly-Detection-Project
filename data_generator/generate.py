import time
import os
import json
import random
from datetime import datetime, timezone
import redis
import logging

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Get Redis connection from environment
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0)

def generate_value(normal_min, normal_max, anomaly_chance=0.05):
    """Generate sensor values with 5% chance of anomaly"""
    if random.random() < anomaly_chance:
        offset = random.uniform(5, 10)
        return random.choice([
            normal_min - offset,
            normal_max + offset
        ])
    
    return round(random.uniform(normal_min, normal_max), 1)

def generate_sensor_data():
    """Create sensor reading with timestamp"""
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    return {
        "timestamp": timestamp,
        "sensor_id": "wtf-pipe-1",
        "temperature": round(generate_value(10, 35), 1),
        "pressure": round(generate_value(1.0, 3.0), 1),
        "flow": round(generate_value(20, 100), 1)
    }

if __name__ == "__main__":
    logger.info("Starting data generator")
    while True:
        data = generate_sensor_data()
        logger.info(f"Generated sensor data: {json.dumps(data)}")
        r.publish('sensor-data', json.dumps(data))
        # Update last received timestamp
        r.set("last_data_received", datetime.now(timezone.utc).isoformat())
        time.sleep(2)