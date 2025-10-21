#!/usr/bin/env bash
set -e

echo "=========================================="
echo "PostgreSQL with Railway Volume Support"
echo "=========================================="

# Download dump file if needed (as root, before switching to postgres)
DUMP_DIR="/docker-entrypoint-initdb.d"
DUMP_FILE="${DUMP_DIR}/backup.dump"

echo "Checking for database dump..."

if [ ! -f "$DUMP_FILE" ] || [ ! -s "$DUMP_FILE" ]; then
  if [ -n "$GITHUB_TOKEN" ]; then
    echo "Downloading dump from GitHub..."
    
    GITHUB_REPO="${GITHUB_REPO:-tyoshilab/bus-delay-predictor-ml}"
    RELEASE_TAG="${RELEASE_TAG:-v1.0.0}"
    ASSET_NAME="${ASSET_NAME:-gtfs_db.dump}"
    
    RELEASE_API_URL="https://api.github.com/repos/$GITHUB_REPO/releases/tags/$RELEASE_TAG"
    
    ASSET_ID=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      "$RELEASE_API_URL" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for asset in data.get('assets', []):
        if asset.get('name') == '$ASSET_NAME':
            print(asset.get('id'))
            break
except:
    pass
" 2>/dev/null)
    
    if [ -n "$ASSET_ID" ]; then
      ASSET_URL="https://api.github.com/repos/$GITHUB_REPO/releases/assets/$ASSET_ID"
      
      if curl -L -f --progress-bar \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/octet-stream" \
        -o "$DUMP_FILE" \
        "$ASSET_URL"; then
        
        SIZE=$(stat -c%s "$DUMP_FILE" 2>/dev/null || stat -f%z "$DUMP_FILE" 2>/dev/null)
        if [ "$SIZE" -gt 100000 ]; then
          echo "✓ Downloaded $SIZE bytes"
        else
          echo "✗ File too small, removing"
          rm -f "$DUMP_FILE"
        fi
      else
        echo "✗ Download failed"
      fi
    else
      echo "✗ Asset not found in release"
    fi
  else
    echo "No GITHUB_TOKEN - database will start empty"
  fi
fi

echo "=========================================="
echo "Starting PostgreSQL"
echo "=========================================="

# Pass control to original PostgreSQL entrypoint
# PGDATA is set to /var/lib/postgresql/data/pgdata (subdirectory)
# This allows Railway to mount /var/lib/postgresql/data as root
# while PostgreSQL writes to the pgdata subdirectory as postgres user
exec docker-entrypoint.sh "$@"
