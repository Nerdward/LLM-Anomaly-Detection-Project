import asyncio
import os
import json
import redis
from datetime import datetime, timedelta, timezone
from langchain_openai import OpenAI
from dotenv import load_dotenv
import logging

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

load_dotenv()

# Ensure HTTP server settings for OpenAI-compatible llama.cpp
open_base_url = os.getenv("OPENAI_API_BASE", "http://localhost:8008/v1")
# The llama_cpp.server does not require an API key by default, but OpenAI client expects one
open_api_key = os.getenv("OPENAI_API_KEY", "unknown")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

class SummaryGenerator:
    def __init__(self):
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=6379,
            db=0
        )
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe('anomalies')

        # Initialize OpenAI-compatible client pointing at llama_cpp.server
        self.llm = OpenAI(
            model_name=os.getenv('MODEL_NAME', 'llama-2-7b-chat.Q4_0.gguf'),
            temperature=float(os.getenv('TEMPERATURE', 0.1)),
            api_key=open_api_key,
            base_url=open_base_url
        )

        self.anomaly_buffer = []

    async def generate_summary(self):
        if not self.anomaly_buffer:
            logger.info("No anomalies detected in the monitoring period")
            return "No anomalies detected in the monitoring period."

        try:
            formatted_anomalies = json.dumps(self.anomaly_buffer, indent=2)
            prompt = f"""
            Generate a concise technical summary of water treatment facility anomalies using this JSON data:
            {formatted_anomalies}

            Guidelines:
            - Use natural, professional language
            - Mention specific time ranges and durations
            - Highlight critical values
            - Group related anomalies
            - Note sensor IDs
            - Never mention JSON structure

            Summary:
            """
            logger.info("Generating summary for %d anomalies", len(self.anomaly_buffer))
            # Invoke via OpenAI adapter over HTTP
            response = await self.llm.ainvoke(prompt)
            summary = response.strip() if isinstance(response, str) else response['choices'][0]['text'].strip()

            # Clear buffer after successful summary
            self.anomaly_buffer = []
            logger.info("Summary generated: %s", summary)
            return summary

        except Exception as e:
            logger.error("Error generating summary: %s", str(e))
            return "Summary generation failed"

    async def process_messages(self):
        logger.info("Starting summary generator")
        summary_interval = int(os.getenv('SUMMARY_INTERVAL', 60))
        while True:
            start_time = datetime.now(timezone.utc)
            end_time = start_time + timedelta(seconds=summary_interval)
            while datetime.now(timezone.utc) < end_time:
                message = self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        anomaly = json.loads(message['data'])
                        self.anomaly_buffer.append(anomaly)
                    except json.JSONDecodeError:
                        logger.error("Failed to decode anomaly message")
                        continue
                await asyncio.sleep(0.01)  # Yield control to event loop
            if self.anomaly_buffer:
                logger.info("Processing %d anomalies in buffer", len(self.anomaly_buffer))
                summary = await self.generate_summary()
                logger.info("System summary: %s", summary)
                self.redis.lpush('summary_history', summary)

if __name__ == "__main__":
    logger.info("Initializing SummaryGenerator")
    generator = SummaryGenerator()
    asyncio.run(generator.process_messages())
