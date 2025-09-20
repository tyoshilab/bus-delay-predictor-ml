# Weather Data Metrics Documentation

This document provides detailed explanations of all metrics contained in the Vancouver weather datasets from Environment and Climate Change Canada.

## Open API
### swagger
https://api.weather.gc.ca/openapi#/

### get climate-stations 
https://api.weather.gc.ca/collections/climate-stations/items?f=json&lang=en-CA&limit=100&properties=ENG_PROV_NAME,ENG_STN_OPERATOR_ACRONYM,ENG_STN_OPERATOR_NAME,HAS_HOURLY_DATA,STATION_NAME,STN_ID&skipGeometry=false&offset=0&ENG_PROV_NAME=BRITISH%20COLUMBIA&HAS_HOURLY_DATA=Y&STATION_NAME=vancouver

### get climate-hourly
https://api.weather.gc.ca/collections/climate-hourly/items?f=json&lang=en-CA&limit=100&properties=DEW_POINT_TEMP,LOCAL_DATE,LOCAL_HOUR,PROVINCE_CODE,STATION_NAME&skipGeometry=false&offset=0&LOCAL_DATE=2025-08-12&LOCAL_MONTH=08&PROVINCE_CODE=BC

## Dataset Overview

### Sources
- **Daily Normals**: `weatherstats_vancouver_normal_daily.csv`
- **Hourly Observations**: `weatherstats_vancouver_hourly.csv`

### Data Disclaimer
The historical weather data, forecast and current conditions graphics are courtesy of Environment and Climate Change Canada. The information presented is combined from multiple Environment and Climate Change Canada data sources and effort is made to be accurate. However, if you find something missing or incorrect please send your feedback. Don't make life or death decisions based on the information you find here.

---

## Hourly Weather Observations Metrics

### Temporal Information
| Metric | Unit | Description |
|--------|------|-------------|
| `date_time_local` | PDT/PST | Local timestamp in Pacific Time |
| `unixtime` | seconds | Unix timestamp (seconds since Jan 1, 1970) |

### Atmospheric Pressure
| Metric | Unit | Description |
|--------|------|-------------|
| `pressure_station` | hPa | Barometric pressure at station level |
| `pressure_sea` | hPa | Sea-level adjusted barometric pressure |

### Wind Measurements
| Metric | Unit | Description |
|--------|------|-------------|
| `wind_dir` | cardinal | Wind direction (E, SE, WSW, etc.) |
| `wind_dir_10s` | degrees | Wind direction in degrees (0-360°), 10-second average |
| `wind_speed` | km/h | Wind speed |
| `wind_gust` | km/h | Maximum wind gust speed |

**Note**: Wind direction is a circular metric where:
- 0° = 360° = North
- 90° = East
- 180° = South  
- 270° = West

### Temperature & Humidity
| Metric | Unit | Description |
|--------|------|-------------|
| `temperature` | °C | Air temperature |
| `relative_humidity` | % | Relative humidity percentage |
| `dew_point` | °C | Dew point temperature |
| `windchill` | index | Wind chill factor (feels-like temperature in cold) |
| `humidex` | index | Humidex (feels-like temperature in heat) |
| `max_air_temp_pst1hr` | °C | Maximum temperature in past hour |
| `min_air_temp_pst1hr` | °C | Minimum temperature in past hour |

### Visibility & Sky Conditions
| Metric | Unit | Description |
|--------|------|-------------|
| `visibility` | meters | Horizontal visibility distance |
| `cloud_cover_4` | oktas | Cloud coverage on 4-point scale |
| `cloud_cover_8` | oktas | Cloud coverage on 8-point scale (traditional) |
| `cloud_cover_10` | tenths | Cloud coverage on 10-point scale |
| `solar_radiation` | W/m² | Solar radiation intensity |

### Air Quality & Health
| Metric | Unit | Description |
|--------|------|-------------|
| `health_index` | index | Air Quality Health Index (1-10+) |

---

## Daily Normal Statistics Metrics

Daily normals represent long-term climate averages based on historical data from 1995-2024.

### Metric Naming Convention
Each daily normal metric follows this pattern:
- `[metric]_v`: **Value** - The statistical measure (mean, max, min)
- `[metric]_s`: **Standard Deviation** - Variability measure
- `[metric]_c`: **Count** - Number of observations used
- `[metric]_d`: **Date Range** - Earliest to latest observation dates

### Temperature Normals
| Base Metric | Description |
|-------------|-------------|
| `max_temperature` | Daily maximum temperature statistics |
| `min_temperature` | Daily minimum temperature statistics |

### Humidity & Dew Point Normals
| Base Metric | Description |
|-------------|-------------|
| `max_dew_point` | Daily maximum dew point statistics |
| `min_dew_point` | Daily minimum dew point statistics |
| `max_relative_humidity` | Daily maximum relative humidity statistics |
| `min_relative_humidity` | Daily minimum relative humidity statistics |

### Wind Normals
| Base Metric | Description |
|-------------|-------------|
| `max_wind_speed` | Daily maximum wind speed statistics |
| `min_wind_speed` | Daily minimum wind speed statistics |

### Precipitation Normals
| Base Metric | Description |
|-------------|-------------|
| `precipitation` | Total daily precipitation (rain + snow equivalent) |
| `rain` | Liquid precipitation only |
| `snow` | Snowfall (water equivalent) |
| `snow_on_ground` | Snow depth on ground |

### Solar Radiation Normals
| Base Metric | Description |
|-------------|-------------|
| `solar_radiation` | Daily solar radiation statistics |

---

## Statistical Measures Explained

### Value (`_v`)
The primary statistical measure - typically the mean (average) over the historical period.

### Standard Deviation (`_s`) 
Measures variability or spread in the data:
- Low values: Consistent conditions
- High values: Variable conditions

### Count (`_c`)
Number of valid observations used in calculations:
- Higher counts = more reliable statistics
- Lower counts may indicate data gaps

### Date Range (`_d`)
Shows the span of historical data:
- Format: "YYYY-MM-DD YYYY-MM-DD" (earliest to latest)
- Longer periods generally provide more reliable normals

---

## Data Quality Notes

### Missing Values
- Hourly data may contain empty cells for certain metrics
- Daily normals occasionally have missing standard deviation or count values
- Always check for null/missing values before analysis

### Circular Statistics for Wind
Wind direction requires special statistical treatment:
- Use circular mean instead of arithmetic mean
- Account for 0°/360° boundary when calculating averages
- Consider wind speed when interpreting direction statistics

### Temporal Coverage
- **Hourly data**: Recent observations (current period)
- **Daily normals**: Long-term averages (1995-2024)
- Data quality varies by metric and time period

---

## Usage Recommendations

### For Analysis
1. **Check data completeness** before statistical analysis
2. **Use circular statistics** for wind direction
3. **Consider seasonal patterns** when interpreting normals
4. **Account for missing values** in calculations

### For Forecasting
1. **Compare current observations** to historical normals
2. **Consider standard deviation** for uncertainty estimates
3. **Use appropriate temporal resolution** (hourly vs daily)

### For Climate Studies
1. **Use long-term normals** for baseline comparisons
2. **Consider data count** when assessing reliability
3. **Account for climate change trends** in recent periods

---

*Last Updated: August 5, 2025*
*Data Source: Environment and Climate Change Canada*
