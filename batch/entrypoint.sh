#!/bin/bash

echo "========================================"
echo "Starting GTFS Batch Processing Container"
echo "========================================"
echo ""

# Don't exit on error during initial checks (allow Python warnings)
set +e

# Validate required environment variables
if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: DATABASE_URL is not set"
  exit 1
fi

if [ -z "$TRANSLINK_API_KEY" ]; then
  echo "WARNING: TRANSLINK_API_KEY is not set. Some jobs may fail."
fi

# Create log directory and files with proper permissions
echo "Setting up log files..."
mkdir -p /app/batch/logs
touch /app/batch/logs/cron_weather.log
touch /app/batch/logs/cron_fetch.log
touch /app/batch/logs/cron_predict.log
chown -R batchuser:batchuser /app/batch/logs
chmod 666 /app/batch/logs/cron_*.log
echo "✓ Log files ready"

# Test database connection (suppress matplotlib warnings)
echo "Testing database connection..."
python -c "
import warnings
warnings.filterwarnings('ignore')
from batch.config.settings import config
from sqlalchemy import create_engine
try:
    engine = create_engine(config.database.database_url)
    conn = engine.connect()
    conn.close()
    print('✓ Database connection: OK')
except Exception as e:
    print(f'✗ Database connection failed: {e}')
    exit(1)
" 2>&1 | grep -E "^(✓|✗)"

# Re-enable exit on error for the rest of the script
set -e

# Download ML model from GitHub Releases if not exists
echo "Checking ML model files..."
MODEL_DIR="/app/files/model"
MODEL_FILE="${MODEL_DIR}/best_delay_model.h5"

if [ ! -f "$MODEL_FILE" ]; then
  echo "Model file not found. Downloading from GitHub Releases..."

  # Create model directory if it doesn't exist
  mkdir -p "$MODEL_DIR"

  # Check if GITHUB_TOKEN is set (required for private repositories)
  if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: GITHUB_TOKEN is not set."
    echo "For private repositories, you must set GITHUB_TOKEN environment variable."
    echo "Create a token at: https://github.com/settings/tokens"
    echo "Required scope: repo (for private repositories)"
    echo "WARNING: Skipping model download. Prediction jobs may fail."
  else
    echo "Using GitHub token for authentication (private repository)"

    # For private repositories, use GitHub API to get the asset download URL
    # Set default values if not provided
    GITHUB_REPO="${GITHUB_REPO:-tyoshilab/bus-delay-predictor-ml}"
    RELEASE_TAG="${RELEASE_TAG:-model-v1.0}"
    ASSET_NAME="${ASSET_NAME:-best_delay_model.h5}"

    echo "Repository: $GITHUB_REPO"
    echo "Release: $RELEASE_TAG"
    echo "Asset: $ASSET_NAME"

    # Get release information
    RELEASE_API_URL="https://api.github.com/repos/$GITHUB_REPO/releases/tags/$RELEASE_TAG"
    echo "Fetching release info from API..."

    # Download release info and extract asset ID
    ASSET_ID=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      "$RELEASE_API_URL" | grep -A 3 "\"name\": \"$ASSET_NAME\"" | grep -oP '"id": \K[0-9]+' | head -1)

    if [ -z "$ASSET_ID" ]; then
      echo "✗ Failed to find asset '$ASSET_NAME' in release '$RELEASE_TAG'"
      echo "Please check that the release and asset exist."
    else
      echo "Asset ID: $ASSET_ID"
      ASSET_URL="https://api.github.com/repos/$GITHUB_REPO/releases/assets/$ASSET_ID"

      # Download model file using API with Accept header for binary content
      echo "Downloading model from GitHub API..."
      if curl -L -f \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/octet-stream" \
        -o "$MODEL_FILE" \
        "$ASSET_URL"; then
        chown batchuser:batchuser "$MODEL_FILE"
        echo "✓ Model downloaded successfully: $MODEL_FILE"
        ls -lh "$MODEL_FILE"
      else
        echo "✗ Failed to download model from: $ASSET_URL"
        echo "WARNING: Prediction jobs may fail without the model file."
      fi
    fi
  fi
else
  echo "✓ Model file already exists: $MODEL_FILE"
  ls -lh "$MODEL_FILE"
fi

# Create cron job file with runtime environment variables
echo "Creating cron configuration..."

# Use a temporary file to safely build the cron configuration
cat > /tmp/gtfs-batch << 'CRONEOF'
# GTFS Batch Processing Cron Jobs

# Set environment variables for cron
SHELL=/bin/bash
PATH=/home/batchuser/.local/bin:/usr/local/bin:/usr/bin:/bin
PYTHONPATH=/app:/home/batchuser/.local/lib/python3.11/site-packages
PYTHONUNBUFFERED=1
PLAYWRIGHT_BROWSERS_PATH=/home/batchuser/.cache/ms-playwright
CRONEOF

# Append environment variables (using printf to handle special characters safely)
printf "DATABASE_URL=%s\n" "$DATABASE_URL" >> /tmp/gtfs-batch
printf "TRANSLINK_API_KEY=%s\n" "$TRANSLINK_API_KEY" >> /tmp/gtfs-batch

# Append the actual cron jobs
cat >> /tmp/gtfs-batch << 'CRONEOF'

# Weather Scraper (every hour at minute 0)
0 * * * * batchuser cd /app && python batch/run.py scrape-weather >> /app/batch/logs/cron_weather.log 2>&1

# GTFS Realtime Fetch (every hour at minute 0 and 30)
0,30 * * * * batchuser cd /app && python batch/run.py load-realtime >> /app/batch/logs/cron_fetch.log 2>&1

# Regional Delay Prediction (every hour at minute 10 and 40)
10,40 * * * * batchuser cd /app && python batch/run.py predict >> /app/batch/logs/cron_predict.log 2>&1

CRONEOF

# Move to final location and set permissions
mv /tmp/gtfs-batch /etc/cron.d/gtfs-batch
chmod 0644 /etc/cron.d/gtfs-batch
echo "✓ Cron configuration created"

# Display cron configuration (without showing sensitive values)
echo ""
echo "Cron jobs configured:"
cat /etc/cron.d/gtfs-batch | grep -E "^(#|[0-9])" | grep -v "DATABASE_URL\|TRANSLINK_API_KEY"
echo ""

# Run initial job if specified
if [ ! -z "$INITIAL_JOB" ]; then
  echo "Running initial job: $INITIAL_JOB"
  cd /app && python batch/run.py $INITIAL_JOB
fi

# Start cron daemon
echo "Starting cron daemon..."
cron

# Wait for cron to fully start
sleep 2

# Verify cron is running
if pgrep -x cron > /dev/null; then
  CRON_PID=$(pgrep -x cron)
  echo "✓ Cron daemon is running (PID: $CRON_PID)"
else
  echo "✗ ERROR: Cron daemon failed to start"
  exit 1
fi

echo ""
echo "=========================================="
echo "Container is ready. Cron jobs are running."
echo "=========================================="
echo "Logs will be written to /app/batch/logs/"
echo ""
echo "Current time: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo ""
echo "Next cron execution times:"
echo "  Weather Scraper:  Every hour at :00"
echo "  GTFS Fetch:       Every hour at :00 and :30"
echo "  Prediction:       Every hour at :10 and :40"
echo ""
echo "Waiting for cron jobs to execute..."
echo "=========================================="

# Use exec to replace shell with tail (for proper signal handling)
exec tail -f /app/batch/logs/cron_*.log /dev/null
