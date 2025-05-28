# Water Treatment Facility Anomaly Detection System

This project implements a real-time anomaly detection and summarization system for a water treatment facility. It generates sensor data (temperature, pressure, flow), detects anomalies (spikes, drifts, dropouts), summarizes anomalies using a large language model (LLM), and provides a REST API to monitor anomalies, summaries, and system status. The system uses Redis for data streaming and storage, FastAPI for the API, and LangChain for LLM integration, all containerized with Docker.

## Setup Instructions

### Prerequisites
- **Docker** and **Docker Compose**: Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for local development.
- **Python 3.12**: Required if running scripts outside Docker.
- **Redis**: Managed via Docker (included in `docker-compose.yml`).
- **LLM Server**: A `llama_cpp.server` instance (or compatible OpenAI API server) running locally at `http://localhost:8008/v1` for summarization.

### Project Structure
```
.
├── api/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── data_generator/
│   ├── generate.py
│   ├── Dockerfile
│   └── requirements.txt
├── anomaly_detector/
│   ├── detector.py
│   ├── Dockerfile
│   └── requirements.txt
├── summary_generator/
│   ├── summarizer.py
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

### Requirements
Each component has a `requirements.txt` file. Example contents (adjust as needed):
```
# api/requirements.txt
fastapi==0.115.0
uvicorn==0.31.0
redis==5.0.8
python-dotenv==1.0.1

# data_generator/requirements.txt
redis==5.0.8
python-dotenv==1.0.1

# anomaly_detector/requirements.txt
redis==5.0.8
python-dotenv==1.0.1

# summary_generator/requirements.txt
redis==5.0.8
python-dotenv==1.0.1
langchain-openai==0.2.2
```

### Installation
1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Set Up Environment Variables**:
   Create a `.env` file in the project root:
   ```bash
   REDIS_HOST=redis
   OPENAI_API_BASE=http://host.docker.internal:8008/v1
   OPENAI_API_KEY=unknown
   MODEL_NAME=llama-2-7b-chat.Q4_0.gguf
   TEMPERATURE=0.1
   SUMMARY_INTERVAL=60
   MAX_BUFFER_SIZE=50
   ```

3. **Set Up LLM Server**:
   - Run a `llama_cpp.server` instance locally, exposing an OpenAI-compatible API at `http://localhost:8008/v1`.
   - Example command (adjust model path):
     ```bash
     python -m llama_cpp.server --model /path/to/llama-2-7b-chat.Q4_0.gguf --host 0.0.0.0 --port 8008
     ```

## Explanation of Detection Thresholds

The anomaly detection system (`detector.py`) identifies three types of anomalies in sensor data (temperature, pressure, flow) from the water treatment facility:

### Spike Anomalies
Sudden, extreme deviations in sensor readings.
- **Temperature**: < 5°C or > 40°C
- **Pressure**: < 0.5 bar or > 4.0 bar
- **Flow**: < 10 L/min or > 120 L/min
- **Example**: A temperature reading of 45°C triggers a spike anomaly.

### Drift Anomalies
Sustained deviations outside normal operating ranges for a specified duration (15 seconds).
- **Temperature**: < 10°C or > 35°C for >15 seconds
- **Pressure**: < 1.0 bar or > 3.0 bar for >15 seconds
- **Flow**: < 20 L/min or > 100 L/min for >15 seconds
- **Example**: A pressure reading of 0.8 bar persisting for 16 seconds triggers a drift anomaly.

### Dropout Anomalies
Gaps in sensor data exceeding 10 seconds.
- **Threshold**: Time between consecutive sensor readings > 10 seconds
- **Example**: If no data is received for 12 seconds, a dropout anomaly is triggered.

These thresholds are defined in `detector.py` under `SPIKE_THRESHOLDS` and `DRIFT_THRESHOLDS`. Adjust them by modifying the script to suit specific operational requirements.

## LangChain Integration

The `summarizer.py` script uses LangChain (`langchain-openai`) to integrate with an LLM for generating concise summaries of detected anomalies:
- **LLM Client**: Configured to connect to an OpenAI-compatible `llama_cpp.server` endpoint (default: `http://localhost:8008/v1`).
- **Model**: Defaults to `llama-2-7b-chat.Q4_0.gguf`, configurable via `MODEL_NAME` environment variable.
- **Async Summarization**: Uses `ainvoke` for non-blocking LLM calls to summarize anomalies every 60 seconds (configurable via `SUMMARY_INTERVAL`).
- **Buffer Management**: Limits the anomaly buffer to 50 entries (configurable via `MAX_BUFFER_SIZE`) to prevent context length errors.
- **Prompt**: Formats anomalies as JSON and instructs the LLM to produce a natural, technical summary with time ranges, critical values, and sensor IDs.

Example summary output:
```
During the period from 2025-05-28T00:01:00Z to 2025-05-28T00:02:00Z, sensor wtf-pipe-1 reported two anomalies. A temperature spike of 45.2°C was detected at 2025-05-28T00:01:23Z, and a pressure drift of 0.8 bar persisted for 16.3 seconds starting at 2025-05-28T00:01:30Z.
```

## API Documentation

The FastAPI server (`app.py`) provides three endpoints to monitor the system:

### 1. GET /anomalies
- **Description**: Retrieve the latest anomalies from Redis (`anomaly_history`).
- **Query Parameter**: `limit` (int, default: 100) – Maximum number of anomalies to return.
- **Response**:
  ```json
  [
    {
      "type": "spike",
      "timestamp": "2025-05-28T00:01:23Z",
      "sensor_id": "wtf-pipe-1",
      "parameter": "temperature",
      "value": 45.2,
      "message": "Temperature spike detected: 45.2"
    },
    ...
  ]
  ```
- **Errors**: 500 if Redis or JSON parsing fails.

### 2. GET /summary
- **Description**: Retrieve all summaries from Redis (`summary_history`).
- **Response**:
  ```json
  {
    "summaries": [
      "During the period from 2025-05-28T00:01:00Z to 2025-05-28T00:02:00Z, ...",
      ...
    ],
    "count": 5
  }
  ```
- **Errors**: 500 if Redis access fails.

### 3. GET /status
- **Description**: Check system health, including Redis connection and data stream activity.
- **Response**:
  ```json
  {
    "data_stream": {
      "healthy": true,
      "last_received": "2025-05-28T00:01:23Z",
      "message": "Data flowing normally"
    },
    "redis": {
      "connected": true,
      "message": "Redis connected"
    }
  }
  ```
- **Errors**: Returns error messages in `redis.message` if Redis is unavailable.

Access the API at `http://localhost:8000` (or the deployed host). Use `/docs` for interactive Swagger UI.

## Local Deployment Instructions

1. **Ensure Prerequisites**:
   - Docker and Docker Compose installed.
   - LLM server running at `http://localhost:8008/v1` (adjust `OPENAI_API_BASE` if different).

2. **Create Directories**:
   Organize the project as shown in the Project Structure section, placing each script and Dockerfile in the appropriate subdirectory.

3. **Build and Run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```
   This starts:
   - `redis`: Redis server (port 6379).
   - `api`: FastAPI server (port 8000).
   - `data-generator`: Generates sensor data every 2 seconds.
   - `anomaly-detector`: Detects anomalies in sensor data.
   - `summary-generator`: Summarizes anomalies every 60 seconds.

4. **Access the API**:
   - Open `http://localhost:8000/docs` for Swagger UI.
   - Test endpoints:
     ```bash
     curl http://localhost:8000/status
     curl http://localhost:8000/anomalies
     curl http://localhost:8000/summary
     ```

5. **Stop the Services**:
   ```bash
   docker-compose down
   ```

## Notes on System Observability and Security

### Observability
- **Logging**: Each component (`generate.py`, `detector.py`, `summarizer.py`, `app.py`) logs to stdout, visible in Docker logs (`docker-compose logs <service>`).
- **System Status**: The `/status` endpoint monitors Redis connectivity and data stream health (data considered stale if not received within 60 seconds).
- **Anomaly History**: Stored in Redis (`anomaly_history`, max 100 entries) and accessible via `/anomalies`.
- **Summary History**: Stored in Redis (`summary_history`) and accessible via `/summary`.
- **Metrics**: Add Prometheus or similar for advanced metrics (e.g., anomaly rates, API response times) if needed.

### Security
- **Environment Variables**: Sensitive settings (e.g., `OPENAI_API_KEY`, `REDIS_HOST`) are loaded from a `.env` file, which should be excluded from version control (add `.env` to `.gitignore`).
- **Network**: Docker Compose uses a default network, isolating services. Expose only the API port (8000) externally.
- **Redis**: No authentication is configured by default. For production, enable Redis authentication or restrict access via network policies.
- **LLM Server**: The `llama_cpp.server` endpoint (`http://localhost:8008/v1`) is assumed local. Secure it with authentication or HTTPS in production.
- **API Security**: Add authentication (e.g., OAuth2) to FastAPI endpoints for production use. Consider rate limiting to prevent abuse.
- **Data Validation**: The system assumes valid JSON from Redis. Add input validation in `detector.py` and `summarizer.py` to handle malformed data robustly.

## Troubleshooting
- **Redis Connection Errors**: Ensure `REDIS_HOST=redis` resolves correctly in Docker. Check `docker-compose logs redis`.
- **LLM Errors**: Verify `llama_cpp.server` is running and accessible at `OPENAI_API_BASE`. Check `summarizer` logs for errors.
- **Context Length Errors**: Adjust `MAX_BUFFER_SIZE` in `.env` if the LLM reports token limit issues.
- **API Errors**: Check `api` logs for FastAPI or Redis issues.

For further assistance, contact the project maintainer or open an issue in the repository.