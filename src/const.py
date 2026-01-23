import os

# Project Root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Root Data Directory
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

# Subdirectories
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, 'processed')
SPLITTED_DATA_DIR = os.path.join(DATA_DIR, 'splitted')
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')

# Weather Data
WEATHER_DATA_DIR = os.path.join(DATA_DIR, 'weather')
WEATHER_RAW_DIR = os.path.join(WEATHER_DATA_DIR, 'raw')
WEATHER_FULL_DIR = os.path.join(WEATHER_DATA_DIR, 'full')

# GTFS Data
GTFS_STATIC_DIR = os.path.join(DATA_DIR, 'google_transit')
STOPS_TXT = os.path.join(GTFS_STATIC_DIR, 'stops.txt')
TRIPS_TXT = os.path.join(GTFS_STATIC_DIR, 'trips.txt')
STOP_TIMES_TXT = os.path.join(GTFS_STATIC_DIR, 'stop_times.txt')
CALENDAR_TXT = os.path.join(GTFS_STATIC_DIR, 'calendar.txt')
SHAPES_TXT = os.path.join(GTFS_STATIC_DIR, 'shapes.txt')

# Specific Data Files
REGIONS_CSV = os.path.join(DATA_DIR, 'gtfs_static.regions.csv')
BOUNDARY_GEOJSON = os.path.join(DATA_DIR, 'local-area-boundary.geojson')
STOP_GOOGLE_TYPES_CSV = os.path.join(DATA_DIR, 'stop_google_types.csv')

# Evaluation Results
EVALUATION_RESULTS_PATH = os.path.join(DATA_DIR, 'evaluation_results.json')
EVALUATION_RESULTS_BASELINE = os.path.join(DATA_DIR, 'evaluation_results_baseline.json')
EVALUATION_RESULTS_XGBOOST = os.path.join(DATA_DIR, 'evaluation_results_xgboost.json')
EVALUATION_RESULTS_LSTM = os.path.join(DATA_DIR, 'evaluation_results_lstm.json')
EVALUATION_RESULTS_STGNN = os.path.join(DATA_DIR, 'evaluation_results_stgnn.json')
