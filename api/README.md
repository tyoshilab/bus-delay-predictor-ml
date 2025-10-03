# GTFS Bus Delay Prediction FastAPI

FastAPI implementation for Vancouver transit bus delay prediction system.

## Features

### 1. Single Route Delay Prediction
- Predict 3-hour delay for specific bus routes
- Uses trained ConvLSTM model with weather integration
- Endpoints:
  - `POST /api/v1/predictions/route`
  - `GET /api/v1/predictions/route/{route_id}`

### 2. Regional Delay Analysis
- Delay predictions for 23 Metro Vancouver municipalities
- Regional performance rankings
- All-regions status dashboard
- Endpoints:
  - `POST /api/v1/regional/predict`
  - `GET /api/v1/regional/predict/{region_id}`
  - `GET /api/v1/regional/status`
  - `GET /api/v1/regional/ranking`
  - `GET /api/v1/regional/regions`

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your database credentials
nano .env
```

### 2. Install Dependencies

```bash
# Install FastAPI requirements
pip install -r requirements-fastapi.txt
```

### 3. Start the Server

```bash
# Using the startup script
./run_api.sh

# Or manually with uvicorn
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Access Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Examples

### Single Route Prediction

**POST Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/predictions/route" \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": "6618",
    "direction_id": 0,
    "lookback_days": 7
  }'
```

**GET Request:**
```bash
curl "http://localhost:8000/api/v1/predictions/route/6618?direction_id=0&lookback_days=7"
```

**Python Example:**
```python
import requests

# POST method
response = requests.post(
    "http://localhost:8000/api/v1/predictions/route",
    json={
        "route_id": "6618",
        "direction_id": 0,
        "lookback_days": 7
    }
)
predictions = response.json()

for pred in predictions['predictions']:
    print(f"{pred['time']}: {pred['delay_minutes']:.2f} minutes")
```

### Regional Prediction

**GET Request:**
```bash
curl "http://localhost:8000/api/v1/regional/predict/vancouver?forecast_hours=3&lookback_days=7"
```

**Python Example:**
```python
import requests

# Regional forecast
response = requests.get(
    "http://localhost:8000/api/v1/regional/predict/vancouver",
    params={
        "forecast_hours": 3,
        "lookback_days": 7
    }
)
forecast = response.json()

print(f"Region: {forecast['region_name']}")
print(f"Summary: {forecast['summary']}")

for pred in forecast['predictions']:
    print(f"{pred['forecast_time']}: {pred['avg_delay_minutes']:.2f} min ({pred['status']})")
```

### All Regions Status

```bash
curl "http://localhost:8000/api/v1/regional/status"
```

```python
import requests

response = requests.get("http://localhost:8000/api/v1/regional/status")
status = response.json()

for region in status['regions']:
    print(f"{region['region_name']}: {region['status']} ({region['avg_delay_minutes']} min)")
```

### Regional Ranking

```bash
curl "http://localhost:8000/api/v1/regional/ranking"
```

```python
import requests

response = requests.get("http://localhost:8000/api/v1/regional/ranking")
ranking = response.json()

for r in ranking['rankings'][:10]:  # Top 10
    print(f"{r['performance_rank']}. {r['region_name']} - Grade: {r['performance_grade']}")
```

## Docker Deployment

### Build Docker Image

```bash
docker build -t gtfs-api .
```

### Run Container

```bash
docker run -d \
  --name gtfs-api \
  -p 8000:8000 \
  --env-file .env \
  gtfs-api
```

### Using Docker Compose

```bash
docker-compose up -d
```

## Production Deployment

### Using Gunicorn + Uvicorn Workers

```bash
gunicorn api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Systemd Service

Create `/etc/systemd/system/gtfs-api.service`:

```ini
[Unit]
Description=GTFS Bus Delay Prediction API
After=network.target

[Service]
Type=notify
User=your_user
Group=your_group
WorkingDirectory=/path/to/GTFS
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable gtfs-api
sudo systemctl start gtfs-api
sudo systemctl status gtfs-api
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Increase timeout for predictions
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
    }
}
```

## Environment Variables

Required environment variables in `.env`:

```bash
# Database connection
DATABASE_URL=postgresql://user:password@host:5432/database
# Or individual settings:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=gtfs_db
DB_USER=your_username
DB_PASSWORD=your_password

# Application settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Model path (optional, default: files/model/best_delay_model.h5)
MODEL_PATH=files/model/best_delay_model.h5
```

## Health Checks

### Global Health Check
```bash
curl "http://localhost:8000/health"
```

### Service-Specific Health Checks
```bash
# Prediction service
curl "http://localhost:8000/api/v1/predictions/health"

# Regional service
curl "http://localhost:8000/api/v1/regional/health"
```

## API Response Examples

### Route Prediction Response

```json
{
  "route_id": "6618",
  "direction_id": 0,
  "current_time": "2025-10-01 13:00:00",
  "latest_data_time": "2025-10-01 12:00:00",
  "predictions": [
    {
      "time": "2025-10-01 13:00:00",
      "delay_seconds": 120.5,
      "delay_minutes": 2.01
    },
    {
      "time": "2025-10-01 14:00:00",
      "delay_seconds": 150.3,
      "delay_minutes": 2.51
    },
    {
      "time": "2025-10-01 15:00:00",
      "delay_seconds": 95.8,
      "delay_minutes": 1.60
    }
  ]
}
```

### Regional Prediction Response

```json
{
  "region_id": "vancouver",
  "region_name": "Vancouver",
  "region_type": "city",
  "current_time": "2025-10-01 13:00:00",
  "lookback_period_days": 7,
  "predictions": [
    {
      "forecast_time": "2025-10-01 14:00:00",
      "hour_of_day": 14,
      "day_of_week": 1,
      "avg_delay_minutes": 2.5,
      "median_delay_minutes": 1.8,
      "probability_delay_over_5min": 15.3,
      "status": "good"
    }
  ],
  "summary": {
    "avg_delay_next_3h": 2.3,
    "overall_status": "good"
  }
}
```

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "ValidationError",
  "message": "Invalid route_id format",
  "timestamp": "2025-10-01T13:00:00",
  "details": {
    "route_id": "Route not found in database"
  }
}
```

HTTP Status Codes:
- `200`: Success
- `400`: Bad Request (validation error)
- `404`: Not Found (route/region not found)
- `500`: Internal Server Error
- `503`: Service Unavailable

## Performance Considerations

### Model Loading
- Models are loaded once at startup and cached in memory
- First request may take longer due to model initialization
- Subsequent requests are much faster

### Database Connection Pooling
- SQLAlchemy connection pooling is used
- Configure pool size in database connector settings

### Caching (Future Enhancement)
- Consider implementing Redis caching for:
  - Regional status (cache for 5-10 minutes)
  - Regional rankings (cache for 1 hour)
  - Frequently requested routes

## Monitoring

### Logging
- All requests are logged with timestamps
- Errors include full stack traces
- Configure log level via `LOG_LEVEL` environment variable

### Metrics (Future Enhancement)
- Integration with Prometheus for metrics
- Request duration histograms
- Error rate monitoring
- Model prediction latency

## Testing

### Manual Testing
```bash
# Test prediction endpoint
curl -X POST "http://localhost:8000/api/v1/predictions/route" \
  -H "Content-Type: application/json" \
  -d '{"route_id": "6618", "direction_id": 0, "lookback_days": 7}'

# Test regional endpoint
curl "http://localhost:8000/api/v1/regional/predict/vancouver"
```

### Automated Testing (TODO)
```bash
pytest tests/api/
```

## Troubleshooting

### Issue: Model file not found
**Error**: `Failed to load model: [Errno 2] No such file or directory`

**Solution**: Ensure model file exists at `files/model/best_delay_model.h5`

### Issue: Database connection failed
**Error**: `Failed to connect to database`

**Solution**: Check `.env` file and database connectivity

### Issue: Permission denied
**Error**: `EACCES: permission denied`

**Solution**: Check file permissions and ownership

## License

MIT License

## Contact

For questions or support, contact the GTFS Analysis Team.
