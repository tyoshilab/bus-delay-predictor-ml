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
WEATHER_DIR = os.path.join(DATA_DIR, 'weather') # Keeps compatibility if used elsewhere, but ideally redundant
WEATHER_RAW_DIR = os.path.join(RAW_DATA_DIR, 'weather')
WEATHER_PROCESSED_DIR = os.path.join(PROCESSED_DATA_DIR, 'weather')
WEATHER_FULL_DIR = os.path.join(WEATHER_PROCESSED_DIR, 'full') # Assuming full meant processed/full or just processed

# GTFS Data
GTFS_REALTIME_DIR = os.path.join(RAW_DATA_DIR, 'GTFS_realtime')
GTFS_STATIC_DIR = os.path.join(RAW_DATA_DIR, 'GTFS_static')
ROUTES_TXT = os.path.join(GTFS_STATIC_DIR, 'routes.txt')
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
