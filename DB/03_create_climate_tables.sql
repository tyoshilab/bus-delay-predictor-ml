-- Climate Data Tables
-- Schema: climate - Contains weather and climate data for Vancouver
-- Data source: Environment and Climate Change Canada weather station data

-- Create schema for climate data
CREATE SCHEMA IF NOT EXISTS climate;
SET search_path TO climate, public;

-- Weather hourly data table
CREATE TABLE IF NOT EXISTS weather_hourly (
    id SERIAL PRIMARY KEY,
    date_time_local TIMESTAMP NOT NULL,
    datetime_utc TIMESTAMP,
    unixtime BIGINT,
    pressure_station NUMERIC(6,2),
    pressure_sea NUMERIC(6,2),
    wind_dir_10s NUMERIC(5,1),
    wind_speed INTEGER,
    relative_humidity INTEGER,
    dew_point NUMERIC(4,1),
    temperature NUMERIC(4,1),
    visibility NUMERIC(8,1),
    cloud_cover_8 NUMERIC(3,1),
    max_air_temp_pst1hr NUMERIC(4,1),
    min_air_temp_pst1hr NUMERIC(4,1),
    humidex_v NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create unique constraint on date_time_local to prevent duplicates
ALTER TABLE weather_hourly 
ADD CONSTRAINT uk_weather_hourly_datetime 
UNIQUE (date_time_local);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_weather_hourly_unixtime 
ON weather_hourly(unixtime);

-- Add comments for documentation
COMMENT ON SCHEMA climate IS 'Climate and weather data for Vancouver region';
COMMENT ON TABLE weather_hourly IS 'Hourly weather observations from Vancouver weather station';

COMMENT ON COLUMN weather_hourly.date_time_local IS 'Local date and time of observation (PDT/PST)';
COMMENT ON COLUMN weather_hourly.datetime_utc IS 'UTC date and time derived from unixtime';
COMMENT ON COLUMN weather_hourly.unixtime IS 'Unix timestamp of observation';
COMMENT ON COLUMN weather_hourly.pressure_station IS 'Station pressure in kPa';
COMMENT ON COLUMN weather_hourly.pressure_sea IS 'Sea level pressure in kPa';
COMMENT ON COLUMN weather_hourly.wind_dir_10s IS 'Wind direction in degrees (10-second average)';
COMMENT ON COLUMN weather_hourly.wind_speed IS 'Wind speed in km/h';
COMMENT ON COLUMN weather_hourly.relative_humidity IS 'Relative humidity as percentage';
COMMENT ON COLUMN weather_hourly.dew_point IS 'Dew point temperature in Celsius';
COMMENT ON COLUMN weather_hourly.temperature IS 'Air temperature in Celsius';
COMMENT ON COLUMN weather_hourly.visibility IS 'Visibility in meters';
COMMENT ON COLUMN weather_hourly.cloud_cover_8 IS 'Cloud cover in oktas (0-8 scale)';
COMMENT ON COLUMN weather_hourly.max_air_temp_pst1hr IS 'Maximum air temperature in past hour (Celsius)';
COMMENT ON COLUMN weather_hourly.min_air_temp_pst1hr IS 'Minimum air temperature in past hour (Celsius)';
COMMENT ON COLUMN weather_hourly.humidex_v IS 'Humidex value (perceived temperature)';

-- Grant permissions (adjust as needed for your application users)
-- GRANT SELECT ON ALL TABLES IN SCHEMA climate TO your_app_user;
-- GRANT INSERT, UPDATE ON weather_hourly TO your_data_loader_user;

RESET search_path;