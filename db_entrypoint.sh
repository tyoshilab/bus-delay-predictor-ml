#!/bin/bash
set -e

echo "=========================================="
echo "PostgreSQL Container with Dump Restore"
echo "=========================================="
echo ""

# Ensure proper ownership of initialization directory
# This script runs as root, but PostgreSQL will run as postgres user
DUMP_DIR="/docker-entrypoint-initdb.d"
DUMP_FILE="${DUMP_DIR}/backup.dump"

# Ensure postgres user can read the init directory
chown -R postgres:postgres "$DUMP_DIR"

echo "Checking database dump file..."

# Check if dump file already exists and is valid
if [ -f "$DUMP_FILE" ] && [ -s "$DUMP_FILE" ]; then
  SIZE=$(stat -c%s "$DUMP_FILE" 2>/dev/null || stat -f%z "$DUMP_FILE" 2>/dev/null)
  if [ "$SIZE" -gt 100000 ]; then
    echo "✓ Valid dump file already exists: $DUMP_FILE"
    ls -lh "$DUMP_FILE"
    # Ensure proper ownership
    chown postgres:postgres "$DUMP_FILE"
    chmod 644 "$DUMP_FILE"
  else
    echo "⚠ Existing dump file is too small ($SIZE bytes), will re-download"
    rm -f "$DUMP_FILE"
  fi
fi

# Download dump if not exists or invalid
if [ ! -f "$DUMP_FILE" ] || [ ! -s "$DUMP_FILE" ]; then
  echo "Dump file not found. Downloading from GitHub Releases..."

  # Check if GITHUB_TOKEN is set (required for private repositories)
  if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: GITHUB_TOKEN is not set."
    echo "For private repositories, you must set GITHUB_TOKEN environment variable."
    echo "Create a token at: https://github.com/settings/tokens"
    echo "Required scope: repo (for private repositories)"
    echo "WARNING: Skipping dump download. Database will start empty."
    touch "$DUMP_FILE"
  else
    echo "Using GitHub token for authentication (private repository)"

    # Set default values if not provided
    GITHUB_REPO="${GITHUB_REPO:-tyoshilab/bus-delay-predictor-ml}"
    RELEASE_TAG="${RELEASE_TAG:-v1.0.0}"
    ASSET_NAME="${ASSET_NAME:-gtfs_db.dump}"

    echo "Repository: $GITHUB_REPO"
    echo "Release: $RELEASE_TAG"
    echo "Asset: $ASSET_NAME"

    # Get release information
    RELEASE_API_URL="https://api.github.com/repos/$GITHUB_REPO/releases/tags/$RELEASE_TAG"
    echo "Fetching release info from API..."

    # Download release info and extract asset ID
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

    if [ -z "$ASSET_ID" ]; then
      echo "✗ Failed to find asset '$ASSET_NAME' in release '$RELEASE_TAG'"
      echo "Please check that the release and asset exist."
      echo "WARNING: Database will start empty."
      touch "$DUMP_FILE"
    else
      echo "Asset ID: $ASSET_ID"
      ASSET_URL="https://api.github.com/repos/$GITHUB_REPO/releases/assets/$ASSET_ID"

      # Download dump file using API with Accept header for binary content
      echo "Downloading database dump from GitHub API..."
      echo "This may take several minutes for large dumps..."
      
      if curl -L -f --progress-bar \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/octet-stream" \
        -o "$DUMP_FILE" \
        "$ASSET_URL"; then

        echo "✓ Dump downloaded successfully: $DUMP_FILE"
        ls -lh "$DUMP_FILE"

        # Verify downloaded file size
        SIZE=$(stat -c%s "$DUMP_FILE" 2>/dev/null || stat -f%z "$DUMP_FILE" 2>/dev/null)
        if [ "$SIZE" -lt 100000 ]; then
          echo "ERROR: Downloaded file is too small ($SIZE bytes)"
          echo "This is likely an error page, not a database dump"
          head -20 "$DUMP_FILE"
          rm -f "$DUMP_FILE"
          touch "$DUMP_FILE"
        else
          echo "✓ File size validation passed: $SIZE bytes"
          # Set proper ownership for postgres user
          chown postgres:postgres "$DUMP_FILE"
          chmod 644 "$DUMP_FILE"
        fi
      else
        echo "✗ Failed to download dump from: $ASSET_URL"
        echo "WARNING: Database will start empty."
        touch "$DUMP_FILE"
      fi
    fi
  fi
fi

echo ""
echo "=========================================="
echo "Starting PostgreSQL..."
echo "=========================================="
echo ""

# IMPORTANT: Execute the original PostgreSQL docker-entrypoint.sh
# This must be run as postgres user, not root
# The postgis/postgis image handles the user switching internally
exec docker-entrypoint.sh "$@"
