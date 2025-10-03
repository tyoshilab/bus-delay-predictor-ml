"""
Import Metro Vancouver Region Boundaries into PostgreSQL

This script imports the actual Metro Vancouver region boundaries from
metro_vancouver_region_boundaries.geojson and metro_vancouver_region_boundaries.csv
into the PostgreSQL database.

Data source: Metro Vancouver Open Data
Features: 23 municipalities and electoral areas
"""

import json
import csv
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from src.data_connection import DatabaseConnector


def load_region_data():
    """Load region names from CSV and geometries from GeoJSON"""

    # Load region names from CSV
    regions = []
    with open('files/region/metro_vancouver_region_boundaries.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Name']:  # Skip empty rows
                regions.append({
                    'name': row['Name'],
                    'center_lat': float(row['Latitude']),
                    'center_lon': float(row['Longitude'])
                })

    # Load geometries from GeoJSON
    with open('files/region/metro_vancouver_region_boundaries.geojson', 'r') as f:
        geojson = json.load(f)

    # Match them
    if len(regions) != len(geojson['features']):
        raise ValueError(
            f"Mismatch: CSV has {len(regions)} regions, "
            f"GeoJSON has {len(geojson['features'])} features"
        )

    # Combine
    combined = []
    for i, region in enumerate(regions):
        feature = geojson['features'][i]
        combined.append({
            'name': region['name'],
            'center_lat': region['center_lat'],
            'center_lon': region['center_lon'],
            'geometry': feature
        })

    return combined


def create_region_id(name: str) -> str:
    """Create a region_id from region name"""
    # Convert "City of Vancouver" → "vancouver"
    # Convert "District of North Vancouver" → "north_vancouver"

    name_lower = name.lower()

    # Remove prefixes
    for prefix in ['city of ', 'district of ', 'township of ', 'village of ', 'municipality']:
        if name_lower.startswith(prefix):
            name_lower = name_lower[len(prefix):]
            break

    # Replace spaces with underscores
    region_id = name_lower.strip().replace(' ', '_')

    return region_id


def get_region_type(name: str) -> str:
    """Determine region type from name"""
    if name.startswith('City of'):
        return 'city'
    elif name.startswith('District of'):
        return 'district'
    elif name.startswith('Township of'):
        return 'township'
    elif name.startswith('Village of'):
        return 'village'
    elif 'Municipality' in name:
        return 'municipality'
    elif 'First Nation' in name:
        return 'first_nation'
    elif 'Electoral Area' in name:
        return 'electoral_area'
    else:
        return 'other'


def import_regions_to_database(dry_run=False):
    """Import regions into PostgreSQL database"""

    print("Loading region data...")
    regions = load_region_data()
    print(f"Loaded {len(regions)} regions")

    if dry_run:
        print("\n=== DRY RUN MODE - No database changes will be made ===\n")

    # Connect to database
    db = DatabaseConnector()

    # Create schema and table
    print("\nCreating database schema...")

    create_schema_sql = """
    -- Enable PostGIS
    CREATE EXTENSION IF NOT EXISTS postgis;

    -- Create schema if not exists
    CREATE SCHEMA IF NOT EXISTS gtfs_static;

    -- Drop existing table
    DROP TABLE IF EXISTS gtfs_static.regions CASCADE;

    -- Create regions table
    CREATE TABLE gtfs_static.regions (
        region_id VARCHAR(50) PRIMARY KEY,
        region_name VARCHAR(100) NOT NULL,
        region_type VARCHAR(50),
        boundary GEOMETRY(Geometry, 4326) NOT NULL,  -- Support both Polygon and MultiPolygon
        center_lat NUMERIC(10, 8),
        center_lon NUMERIC(11, 8),
        population INTEGER,
        area_km2 NUMERIC(10, 2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create indexes
    CREATE INDEX idx_regions_boundary ON gtfs_static.regions USING GIST(boundary);
    CREATE INDEX idx_regions_name ON gtfs_static.regions(region_name);
    CREATE INDEX idx_regions_type ON gtfs_static.regions(region_type);

    COMMENT ON TABLE gtfs_static.regions IS 'Metro Vancouver region boundaries (23 municipalities)';
    """

    if not dry_run:
        with db.get_connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(create_schema_sql)
        print("✓ Schema created")
    else:
        print("  [DRY RUN] Would create schema and table")

    # Insert regions
    print("\nInserting regions...")

    # Use INSERT ... ON CONFLICT to handle duplicates
    insert_sql = """
    INSERT INTO gtfs_static.regions
        (region_id, region_name, region_type, boundary, center_lat, center_lon)
    VALUES
        (%s, %s, %s, ST_GeomFromGeoJSON(%s), %s, %s)
    ON CONFLICT (region_id) DO UPDATE SET
        region_name = EXCLUDED.region_name,
        region_type = EXCLUDED.region_type,
        boundary = EXCLUDED.boundary,
        center_lat = EXCLUDED.center_lat,
        center_lon = EXCLUDED.center_lon,
        updated_at = CURRENT_TIMESTAMP
    """

    for i, region in enumerate(regions):
        region_id = create_region_id(region['name'])
        region_type = get_region_type(region['name'])

        # Convert geometry to GeoJSON string
        geojson_str = json.dumps(region['geometry'])

        print(f"  {i+1:2d}. {region_id:30s} ({region['name']})")

        if not dry_run:
            with db.get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    try:
                        cur.execute(
                            insert_sql,
                            (
                                region_id,
                                region['name'],
                                region_type,
                                geojson_str,
                                region['center_lat'],
                                region['center_lon']
                            )
                        )
                    except Exception as e:
                        print(f"      ⚠ Warning: {e}")
                        continue

    print(f"\n✓ Inserted {len(regions)} regions")

    # Add region_id to stops table
    print("\nAdding region_id column to gtfs_stops...")

    alter_stops_sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'gtfs_static'
            AND table_name = 'gtfs_stops'
            AND column_name = 'region_id'
        ) THEN
            ALTER TABLE gtfs_static.gtfs_stops
            ADD COLUMN region_id VARCHAR(50) REFERENCES gtfs_static.regions(region_id);

            CREATE INDEX idx_stops_region ON gtfs_static.gtfs_stops(region_id);
        END IF;
    END $$;
    """

    if not dry_run:
        with db.get_connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(alter_stops_sql)
        print("✓ Added region_id column to gtfs_stops")
    else:
        print("  [DRY RUN] Would add region_id column")

    # Map stops to regions
    print("\nMapping stops to regions...")

    mapping_sql = """
    UPDATE gtfs_static.gtfs_stops s
    SET region_id = r.region_id
    FROM gtfs_static.regions r
    WHERE ST_Within(
        ST_SetSRID(ST_MakePoint(s.stop_lon, s.stop_lat), 4326),
        r.boundary
    )
    """

    if not dry_run:
        with db.get_connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(mapping_sql)

                # Get mapping statistics
                cur.execute("""
                    SELECT
                        COUNT(*) as total_stops,
                        COUNT(region_id) as mapped_stops
                    FROM gtfs_static.gtfs_stops
                """)
                result = cur.fetchone()
                total, mapped = result
                unmapped = total - mapped

                print(f"✓ Mapping completed")
                print(f"  Total stops: {total:,}")
                print(f"  Mapped stops: {mapped:,} ({mapped/total*100:.1f}%)")
                print(f"  Unmapped stops: {unmapped:,} ({unmapped/total*100:.1f}%)")
    else:
        print("  [DRY RUN] Would map stops to regions")

    # Create materialized view
    print("\nCreating stops_with_regions_mv...")

    mv_sql = """
    DROP MATERIALIZED VIEW IF EXISTS gtfs_static.stops_with_regions_mv CASCADE;

    CREATE MATERIALIZED VIEW gtfs_static.stops_with_regions_mv AS
    SELECT
        s.stop_id,
        s.stop_code,
        s.stop_name,
        s.stop_lat,
        s.stop_lon,
        s.zone_id,
        r.region_id,
        r.region_name,
        r.region_type,
        ST_SetSRID(ST_MakePoint(s.stop_lon, s.stop_lat), 4326) as stop_location
    FROM gtfs_static.gtfs_stops s
    LEFT JOIN gtfs_static.regions r USING (region_id);

    CREATE INDEX idx_stops_regions_mv_region ON gtfs_static.stops_with_regions_mv(region_id);
    CREATE INDEX idx_stops_regions_mv_location ON gtfs_static.stops_with_regions_mv USING GIST(stop_location);
    """

    if not dry_run:
        with db.get_connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(mv_sql)
        print("✓ Created materialized view")
    else:
        print("  [DRY RUN] Would create materialized view")

    # Show region summary
    print("\n" + "="*70)
    print("Region-Stop Mapping Summary")
    print("="*70)

    if not dry_run:
        summary_query = """
        SELECT
            r.region_id,
            r.region_name,
            r.region_type,
            COUNT(s.stop_id) as stop_count
        FROM gtfs_static.regions r
        LEFT JOIN gtfs_static.gtfs_stops s USING (region_id)
        GROUP BY r.region_id, r.region_name, r.region_type
        ORDER BY stop_count DESC, r.region_name
        """

        import pandas as pd
        df = db.read_sql(summary_query)

        print(df.to_string(index=False))
        print(f"\nTotal regions: {len(df)}")
        print(f"Total stops across all regions: {df['stop_count'].sum():,}")
    else:
        print("  [DRY RUN] Would display region summary")

    print("\n" + "="*70)
    print("✓ Import completed successfully!")
    print("="*70)

    print("\nNext steps:")
    print("  1. Run: psql -d <database> -f DB/07_create_regional_delay_views.sql")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Import Metro Vancouver region boundaries into PostgreSQL"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    try:
        import_regions_to_database(dry_run=args.dry_run)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
