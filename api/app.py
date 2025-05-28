import json
import os
import redis
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
r = redis.Redis(
    host=os.getenv("REDIS_HOST", 'redis'),
    port=6379,
    db=0,
    decode_responses=True
)

MAX_ANOMALIES = 100  # Keep last 100 anomalies
STATUS_WINDOW = 60   # Seconds considered "recent" for status

ANOMALY_HISTORY_KEY = "anomaly_history"
SUMMARY_HISTORY_KEY = "summary_history"

def get_anomaly_history():
    """Retrieve complete anomaly history"""
    try:
        return r.lrange(ANOMALY_HISTORY_KEY, 0, -1)
    except Exception as e:
        raise HTTPException(500, f"Error retrieving anomalies: {str(e)}")
    

def get_system_status():
    """Check health of system components"""
    status = {
        "data_stream": {
            "healthy": False,
            "last_received": None,
            "message": ""
        },
        "redis": {
            "connected": False,
            "message": ""
        }
    }

    # Check Redis connection
    try:
        r.ping()
        status["redis"]["connected"] = True
        status["redis"]["message"] = "Redis connected"
    except Exception as e:
        status["redis"]["message"] = f"Redis error: {str(e)}"
        return status

    # Check data stream
    last_received = r.get("last_data_received")
    if last_received:
        last_ts = datetime.fromisoformat(last_received)
        elapsed = (datetime.now(timezone.utc) - last_ts).total_seconds()
        status["data_stream"]["last_received"] = last_received
        status["data_stream"]["healthy"] = elapsed < STATUS_WINDOW
        status["data_stream"]["message"] = (
            "Data flowing normally" if status["data_stream"]["healthy"]
            else f"No data received for {elapsed:.1f} seconds"
        )
    else:
        status["data_stream"]["message"] = "No data received yet"

    return status

@app.get("/anomalies")
async def get_anomalies(limit: int = 100):
    try:
        anomalies = get_anomaly_history()
        parsed = [json.loads(a) for a in anomalies[:limit]]
        return JSONResponse(content=parsed[::-1])  # Return newest first
    except Exception as e:
        raise HTTPException(500, f"Error processing anomalies: {str(e)}")

@app.get("/summary")
async def get_summary():
    try:
        summaries = r.lrange(SUMMARY_HISTORY_KEY, 0, -1)
        if not summaries:
            return JSONResponse(content={"message": "No summaries available"})
        return JSONResponse(content={
            "summaries": summaries[::-1],  # Newest first
            "count": len(summaries)
        })
    except Exception as e:
        raise HTTPException(500, f"Error retrieving summaries: {str(e)}")

@app.get("/status")
async def get_status():
    return JSONResponse(content=get_system_status())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)