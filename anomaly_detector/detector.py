import json
import os
import redis
from datetime import datetime, timedelta
import logging

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

MAX_ANOMALIES = 100 
# Threshold configurations
SPIKE_THRESHOLDS = {
    "temperature": {"min": 5, "max": 40},
    "pressure": {"min": 0.5, "max": 4.0},
    "flow": {"min": 10, "max": 120}
}

DRIFT_THRESHOLDS = {
    "temperature": {"min": 10, "max": 35, "duration": 15},
    "pressure": {"min": 1.0, "max": 3.0, "duration": 15},
    "flow": {"min": 20, "max": 100, "duration": 15}
}

# Get Redis connection from environment
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')

class AnomalyDetector:
    def __init__(self):
        self.redis = redis.Redis(host=REDIS_HOST, port=6379, db=0)
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe("sensor-data")

        # State tracking
        self.last_received = None
        self.drift_states = {
            "temperature": {"start": None, "current_duration": 0},
            "pressure": {"start": None, "current_duration": 0},
            "flow": {"start": None, "current_duration": 0}
        }

    def detect_spike(self, data):
        anomalies = []
        for param in ["temperature", "pressure", "flow"]:
            value = data[param]
            thresholds = SPIKE_THRESHOLDS[param]
            if value < thresholds["min"] or value > thresholds["max"]:
                anomalies.append(
                    {
                        "type": "spike",
                        "timestamp": data["timestamp"],
                        "sensor_id": data["sensor_id"],
                        "parameter": param,
                        "value": value,
                        "message": f"{param.capitalize()} spike detected: {value}"
                    }
                )

        return anomalies
    
    def detect_drift(self, data):
        anomalies = []
        now = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

        for param in ["temperature", "pressure", "flow"]:
            value = data[param]
            thresholds = DRIFT_THRESHOLDS[param]
            state = self.drift_states[param]

            # Check if value is outside normal range
            if value < thresholds["min"] or value > thresholds["max"]:
                if not state["start"]:
                    state["start"] = now
                
                state["current_duration"] = (now - state["start"]).total_seconds()

                if state["current_duration"] > thresholds["duration"]:
                    anomalies.append({
                        "type": "drift",
                        "timestamp": data["timestamp"],
                        "sensor_id": data["sensor_id"],
                        "parameter": param,
                        "value": value,
                        "duration_seconds": state["current_duration"],
                        "message": f"{param.capitalize()} drift detected for {state['current_duration']:.1f}s"
                    })

            else:
                state["start"] = None
                state["current_duration"] = 0
        
        return anomalies
    
    def detect_dropout(self, data):
        now = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

        if self.last_received and (now - self.last_received) > timedelta(seconds=10):
            return [{
                "type": "dropout",
                "timestamp": data["timestamp"],
                "sensor_id": data["sensor_id"],
                "duration_seconds": (now - self.last_received).total_seconds(),
                "message": "Sensor dropout detected"
            }]
        
        self.last_received = now
        return []
    
    def process_message(self, message):
        try:
            data = json.loads(message["data"])
            anomalies = []

            anomalies += self.detect_spike(data)
            anomalies += self.detect_drift(data)
            anomalies += self.detect_dropout(data)

            for anomaly in anomalies:
                logger.info(f"Detected anomaly: {json.dumps(anomaly)}")
                self.redis.publish("anomalies", json.dumps(anomaly))
                # After anomaly detection
                self.redis.lpush('anomaly_history', json.dumps(anomaly))
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")

    def run(self):
        logger.info("Starting anomaly detector")
        for message in self.pubsub.listen():
            if message["type"] == 'message':
                self.process_message(message)

if __name__ == "__main__":
    detector = AnomalyDetector()
    detector.run()