import json
from src.data_connection import DatabaseConnector

def main():
    db_connector = DatabaseConnector()
    df_stops = db_connector.read_sql("""
    SELECT s.*, 
        ARRAY_AGG(DISTINCT t.trip_headsign) as trip_headsigns,
        ARRAY_AGG(DISTINCT r.route_short_name) as route_short_names
    FROM gtfs_static.gtfs_stops s
    inner join gtfs_static.gtfs_stop_times st using (stop_id)
    inner join gtfs_static.gtfs_trips_static t using (trip_id)
    inner join gtfs_static.gtfs_routes r using (route_id)
    GROUP BY s.stop_id, s.*
    """)

    features = []
    for row in df_stops.itertuples():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row.stop_lon, row.stop_lat]
            },
            "properties": {
                "stop_lat": row.stop_lat,
                "wheelchair_boarding": row.wheelchair_boarding,
                "stop_code": row.stop_code,
                "stop_lon": row.stop_lon,
                "stop_id": row.stop_id,
                "stop_url": row.stop_url,
                "parent_station": row.parent_station,
                "stop_desc": row.stop_desc,
                "stop_name": row.stop_name,
                "location_type": row.location_type,
                "zone_id": row.zone_id,
                "trip_headsigns": row.trip_headsigns,
                "route_short_names": row.route_short_names
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "name": "stops",
        "crs": {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
            }
        },
        "features": features
    }

    with open('stops.geojson', 'w') as f:
        json.dump(geojson, f, indent=2)

if __name__ == "__main__":
    main()