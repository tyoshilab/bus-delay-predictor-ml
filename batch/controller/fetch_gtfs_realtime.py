#!/usr/bin/env python3
"""
GTFS Realtime Data Fetcher
Fetches GTFS Realtime protobuf data from TransLink API and stores to disk.
"""

import sys
import os
import requests
import time
from datetime import datetime
from pathlib import Path

# Add paths for imports
controller_dir = os.path.dirname(os.path.abspath(__file__))
project_root = Path(controller_dir).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, controller_dir)  # Add controller dir for direct gtfs_realtime_pb2 import

try:
    import gtfs_realtime_pb2
except ImportError:
    print("Error: gtfs_realtime_pb2.py not found. Please generate it from gtfs-realtime.proto")
    sys.exit(1)

class GTFSRealtimeFetcher:
    def __init__(self, api_key=None, base_url="https://gtfsapi.translink.ca"):
        """
        Initialize GTFS Realtime fetcher.
        
        Args:
            api_key (str): TransLink API key (if None, will use environment variable)
            base_url (str): Base URL for TransLink GTFS API
        """
        self.api_key = api_key or os.getenv('TRANSLINK_API_KEY')
        self.base_url = base_url
        self.feeds = {
            'trip_updates': '/v3/gtfsrealtime',
            'vehicle_positions': '/v3/gtfsposition', 
            'alerts': '/v3/gtfsalerts'
        }
        # On Heroku, only /tmp is writable. Allow override via REALTIME_STORAGE_DIR.
        storage_root = os.getenv('REALTIME_STORAGE_DIR', '/app/proto/realtime_data')
        # Fallback to /tmp if default path is not writable
        try:
            Path(storage_root).mkdir(parents=True, exist_ok=True)
        except Exception:
            storage_root = '/tmp/realtime_data'
        self.storage_dir = Path(storage_root)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.api_key:
            print("Warning: No API key provided. Set TRANSLINK_API_KEY environment variable or pass api_key parameter.")
    
    def fetch_feed(self, feed_type, timeout=30):
        """
        Fetch a specific GTFS Realtime feed.
        
        Args:
            feed_type (str): Type of feed ('trip_updates', 'vehicle_positions', 'alerts')
            timeout (int): Request timeout in seconds
            
        Returns:
            bytes: Raw protobuf data or None if failed
        """
        if feed_type not in self.feeds:
            print(f"Error: Unknown feed type '{feed_type}'. Must be one of: {list(self.feeds.keys())}")
            return None
        
        url = f"{self.base_url}{self.feeds[feed_type]}"
        headers = {
            'User-Agent': 'GTFS-RT-Fetcher/1.0',
            'Accept': 'application/x-protobuf'
        }
        
        params = {}
        if self.api_key:
            params['apikey'] = self.api_key
        
        try:
            print(f"Fetching {feed_type} from {url}")
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                print(f"Successfully fetched {feed_type}: {len(response.content)} bytes")
                return response.content
            elif response.status_code == 401:
                print(f"Error: Unauthorized (401). Check your API key.")
                return None
            elif response.status_code == 429:
                print(f"Error: Rate limited (429). Please wait before retrying.")
                return None
            else:
                print(f"Error: HTTP {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"Error: Request timeout after {timeout} seconds")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error: Request failed - {e}")
            return None
    
    def validate_protobuf(self, data):
        """
        Validate that the data is a valid GTFS Realtime protobuf.
        
        Args:
            data (bytes): Raw protobuf data
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            feed_message = gtfs_realtime_pb2.FeedMessage()
            feed_message.ParseFromString(data)
            
            # Basic validation
            if not feed_message.HasField('header'):
                print("Error: Invalid protobuf - missing header")
                return False
            
            if len(feed_message.entity) == 0:
                print("Warning: No entities in feed")
            
            print(f"Valid protobuf: version={feed_message.header.gtfs_realtime_version}, "
                  f"entities={len(feed_message.entity)}, "
                  f"timestamp={feed_message.header.timestamp}")
            
            return True
            
        except Exception as e:
            print(f"Error: Invalid protobuf data - {e}")
            return False
    
    def save_to_disk(self, data, feed_type, timestamp=None):
        """
        Save protobuf data to disk with timestamp.
        
        Args:
            data (bytes): Raw protobuf data
            feed_type (str): Type of feed
            timestamp (datetime): Timestamp for filename (defaults to now)
            
        Returns:
            Path: Path to saved file or None if failed
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Create timestamped filename
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"translink_{feed_type}_{timestamp_str}.pb"
        filepath = self.storage_dir / filename
        
        try:
            with open(filepath, 'wb') as f:
                f.write(data)
            
            print(f"Saved {feed_type} to {filepath} ({len(data)} bytes)")
            
            # Also save as latest (for convenience)
            latest_filepath = self.storage_dir / f"translink_{feed_type}_latest.pb"
            with open(latest_filepath, 'wb') as f:
                f.write(data)
            
            return filepath
            
        except IOError as e:
            print(f"Error: Failed to save {feed_type} to disk - {e}")
            return None
    
    def fetch_all_feeds(self, save_to_disk=True, validate=True):
        """
        Fetch all GTFS Realtime feeds.
        
        Args:
            save_to_disk (bool): Whether to save feeds to disk
            validate (bool): Whether to validate protobuf data
            
        Returns:
            dict: Dictionary with feed_type -> (data, filepath) mappings
        """
        results = {}
        timestamp = datetime.now()
        
        for feed_type in self.feeds.keys():
            print(f"\n{'='*60}")
            print(f"Fetching {feed_type.upper()}")
            print(f"{'='*60}")
            
            data = self.fetch_feed(feed_type)
            
            if data is None:
                print(f"Failed to fetch {feed_type}")
                results[feed_type] = (None, None)
                continue
            
            if validate and not self.validate_protobuf(data):
                print(f"Invalid protobuf data for {feed_type}")
                results[feed_type] = (data, None)
                continue
            
            filepath = None
            if save_to_disk:
                filepath = self.save_to_disk(data, feed_type, timestamp)
            
            results[feed_type] = (data, filepath)
            
            # Small delay between requests to be respectful
            time.sleep(1)
        
        return results
    
    def cleanup_old_files(self, days_to_keep=7):
        """
        Clean up old protobuf files.
        
        Args:
            days_to_keep (int): Number of days to keep files
        """
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        
        for filepath in self.storage_dir.glob("*.pb"):
            if filepath.name.endswith("_latest.pb"):
                continue  # Keep latest files
            
            if filepath.stat().st_mtime < cutoff_time:
                try:
                    filepath.unlink()
                    print(f"Deleted old file: {filepath}")
                except OSError as e:
                    print(f"Error deleting {filepath}: {e}")

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch GTFS Realtime data from TransLink')
    parser.add_argument('--api-key', help='TransLink API key (or set TRANSLINK_API_KEY env var)')
    parser.add_argument('--feeds', nargs='+', choices=['trip_updates', 'vehicle_positions', 'alerts'],
                       default=['trip_updates', 'vehicle_positions', 'alerts'],
                       help='Which feeds to fetch (default: all)')
    parser.add_argument('--no-save', action='store_true', help='Do not save to disk')
    parser.add_argument('--no-validate', action='store_true', help='Skip protobuf validation')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='Clean up files older than DAYS')
    
    args = parser.parse_args()
    
    fetcher = GTFSRealtimeFetcher(api_key=args.api_key)
    
    if args.cleanup:
        print(f"Cleaning up files older than {args.cleanup} days...")
        fetcher.cleanup_old_files(args.cleanup)
        return
    
    # Temporarily override feeds if specific ones requested
    if set(args.feeds) != set(fetcher.feeds.keys()):
        original_feeds = fetcher.feeds.copy()
        fetcher.feeds = {k: v for k, v in original_feeds.items() if k in args.feeds}
    
    results = fetcher.fetch_all_feeds(
        save_to_disk=not args.no_save,
        validate=not args.no_validate
    )
    
    # Summary
    print(f"\n{'='*60}")
    print("FETCH SUMMARY")
    print(f"{'='*60}")
    
    success_count = sum(1 for data, _ in results.values() if data is not None)
    total_count = len(results)
    
    print(f"Successfully fetched: {success_count}/{total_count} feeds")
    
    for feed_type, (data, filepath) in results.items():
        status = "✓" if data is not None else "✗"
        size = f"({len(data)} bytes)" if data else ""
        file_info = f" -> {filepath}" if filepath else ""
        print(f"  {status} {feed_type} {size}{file_info}")

if __name__ == "__main__":
    main()