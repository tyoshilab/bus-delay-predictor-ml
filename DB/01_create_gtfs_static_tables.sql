-- Project Name : noname
-- Date/Time    : 2025/09/14 1:55:08
-- Author       : loveu
-- RDBMS Type   : PostgreSQL
-- Application  : A5:SQL Mk-2

create schema if not exists gtfs_static;
SET search_path TO gtfs_static, public;

create table if not exists gtfs_directions (
  direction_id INTEGER
  , direction VARCHAR(100)
  , route_id VARCHAR(20)
  , route_short_name VARCHAR(50)
  , LineIdConst VARCHAR(20)
) ;

create index if not exists idx_direction
  on gtfs_directions(direction_id);

alter table gtfs_directions
  add constraint gtfs_directions_PKC primary key (direction_id);

create table if not exists gtfs_agency (
  agency_id character varying(10) not null
  , agency_name character varying(100) not null
  , agency_url character varying(255)
  , agency_timezone character varying(50) not null
  , agency_lang character varying(5)
  , agency_fare_url character varying(255)
) ;

create unique index if not exists gtfs_agency_PKI
  on gtfs_agency(agency_id);

alter table gtfs_agency
  add constraint gtfs_agency_PKC primary key (agency_id);

create table if not exists gtfs_calendar (
  service_id character varying(20) not null
  , monday integer not null
  , tuesday integer not null
  , wednesday integer not null
  , thursday integer not null
  , friday integer not null
  , saturday integer not null
  , sunday integer not null
  , start_date date not null
  , end_date date not null
) ;

create unique index if not exists gtfs_calendar_PKI
  on gtfs_calendar(service_id);

alter table gtfs_calendar
  add constraint gtfs_calendar_PKC primary key (service_id);

create table if not exists gtfs_calendar_dates (
  service_id character varying(20) not null
  , date date not null
  , exception_type integer not null
) ;

create unique index if not exists gtfs_calendar_dates_PKI
  on gtfs_calendar_dates(service_id,date);

alter table gtfs_calendar_dates
  add constraint gtfs_calendar_dates_PKC primary key (service_id,date);

create table if not exists gtfs_feed_info (
  feed_publisher_name character varying(100) not null
  , feed_publisher_url character varying(255) not null
  , feed_lang character varying(5) not null
  , feed_start_date date
  , feed_end_date date
  , feed_version character varying(50)
) ;

create table if not exists gtfs_routes (
  route_id character varying(20) not null
  , agency_id character varying(10)
  , route_short_name character varying(50)
  , route_long_name character varying(100)
  , route_desc text
  , route_type integer not null
  , route_url character varying(255)
  , route_color character varying(6)
  , route_text_color character varying(6)
) ;

create index if not exists idx_routes_agency
  on gtfs_routes(agency_id);

create unique index if not exists gtfs_routes_PKI
  on gtfs_routes(route_id);

alter table gtfs_routes
  add constraint gtfs_routes_PKC primary key (route_id);

create table if not exists gtfs_shapes (
  shape_id character varying(20) not null
  , shape_pt_lat numeric(10, 8) not null
  , shape_pt_lon numeric(11, 8) not null
  , shape_pt_sequence integer not null
  , shape_dist_traveled numeric(10, 4)
) ;

create unique index if not exists gtfs_shapes_PKI
  on gtfs_shapes(shape_id,shape_pt_sequence);

alter table gtfs_shapes
  add constraint gtfs_shapes_PKC primary key (shape_id,shape_pt_sequence);

create table if not exists gtfs_stop_times (
  trip_id character varying(20) not null
  , arrival_time time without time zone
  , departure_time time without time zone
  , stop_id character varying(20)
  , stop_sequence integer not null
  , stop_headsign character varying(100)
  , pickup_type integer default 0
  , drop_off_type integer default 0
  , shape_dist_traveled numeric(10, 4)
  , timepoint integer default 0
  , arrival_day_offset integer default 0
  , departure_day_offset integer default 0
) ;

comment on column gtfs_stop_times.arrival_day_offset is 'Day offset for arrival time. 0 = same service day, 1 = next day. Used for times >= 24:00:00 in GTFS.';
comment on column gtfs_stop_times.departure_day_offset is 'Day offset for departure time. 0 = same service day, 1 = next day. Used for times >= 24:00:00 in GTFS.';

create index if not exists idx_stop_times_stop
  on gtfs_stop_times(stop_id);

create index if not exists idx_stop_times_trip
  on gtfs_stop_times(trip_id);

create index if not exists idx_stop_times_arrival_with_offset
  on gtfs_stop_times(stop_id, arrival_day_offset, arrival_time);

create unique index if not exists gtfs_stop_times_PKI
  on gtfs_stop_times(trip_id,stop_sequence);

alter table gtfs_stop_times
  add constraint gtfs_stop_times_PKC primary key (trip_id,stop_sequence);

create table if not exists gtfs_stops (
  stop_id character varying(20) not null
  , stop_code character varying(20)
  , stop_name character varying(100) not null
  , stop_desc text
  , stop_lat numeric(10, 8)
  , stop_lon numeric(11, 8)
  , zone_id character varying(20)
  , stop_url character varying(255)
  , location_type integer default 0
  , parent_station character varying(20)
  , wheelchair_boarding integer default 0
) ;

create index if not exists idx_stops_location
  on gtfs_stops(stop_lat,stop_lon);

create unique index if not exists gtfs_stops_PKI
  on gtfs_stops(stop_id);

alter table gtfs_stops
  add constraint gtfs_stops_PKC primary key (stop_id);

create table if not exists gtfs_transfers (
  from_stop_id character varying(20) not null
  , to_stop_id character varying(20) not null
  , transfer_type integer not null
  , min_transfer_time integer
  , from_trip_id character varying(20)
  , to_trip_id character varying(20)
) ;

create unique index if not exists gtfs_transfers_PKI
  on gtfs_transfers(from_stop_id,to_stop_id);

alter table gtfs_transfers
  add constraint gtfs_transfers_PKC primary key (from_stop_id,to_stop_id);

create table if not exists gtfs_trips_static (
  trip_id character varying(20) not null
  , route_id character varying(20)
  , service_id character varying(20)
  , trip_headsign character varying(100)
  , trip_short_name character varying(50)
  , direction_id integer
  , block_id character varying(20)
  , shape_id character varying(20)
  , wheelchair_accessible integer default 0
  , bikes_allowed integer default 0
) ;

create index if not exists idx_trips_route
  on gtfs_trips_static(route_id);

create index if not exists idx_trips_service
  on gtfs_trips_static(service_id);

create unique index if not exists gtfs_trips_static_PKI
  on gtfs_trips_static(trip_id);

alter table gtfs_trips_static
  add constraint gtfs_trips_static_PKC primary key (trip_id);

create table if not exists gtfs_rt_alert_text (
  alert_url_id serial not null
  , alert_id integer not null
  , text_type text not null
  , text text
  , language text
) ;

create unique index if not exists gtfs_rt_alert_text_PKI
  on gtfs_rt_alert_text(alert_url_id);

alter table gtfs_rt_alert_text
  add constraint gtfs_rt_alert_text_PKC primary key (alert_url_id);

create table if not exists gtfs_rt_alert_active_periods (
  alert_period_id serial not null
  , alert_id integer not null
  , period_time bigint
) ;

create unique index if not exists gtfs_rt_alert_active_periods_PKI
  on gtfs_rt_alert_active_periods(alert_period_id);

alter table gtfs_rt_alert_active_periods
  add constraint gtfs_rt_alert_active_periods_PKC primary key (alert_period_id);

create table if not exists gtfs_rt_alert_informed_entities (
  alert_informed_id serial not null
  , alert_id integer not null
  , agency_id text
  , route_id text
  , route_type integer
  , stop_id text
) ;

create unique index if not exists gtfs_rt_alert_informed_entities_PKI
  on gtfs_rt_alert_informed_entities(alert_informed_id);

alter table gtfs_rt_alert_informed_entities
  add constraint gtfs_rt_alert_informed_entities_PKC primary key (alert_informed_id);

create table if not exists gtfs_rt_alerts (
  alert_id serial not null
  , feed_entity_id integer not null
  , cause text not null
  , effect text not null
  , severity_level text not null
  , created_at timestamp(6) with time zone default now()
) ;

create index if not exists idx_alerts_cause_effect
  on gtfs_rt_alerts(cause,effect);

create index if not exists idx_alerts_feed_entity
  on gtfs_rt_alerts(feed_entity_id);

create index if not exists idx_rt_alerts_created_at
  on gtfs_rt_alerts(created_at);

create unique index if not exists gtfs_rt_alerts_PKI
  on gtfs_rt_alerts(alert_id);

alter table gtfs_rt_alerts
  add constraint gtfs_rt_alerts_PKC primary key (alert_id);

create table if not exists gtfs_rt_feed_entities (
  id serial not null
  , feed_message_id integer not null
  , entity_id text not null
  , is_deleted boolean default false
  , entity_type text not null
  , created_at timestamp(6) with time zone default now()
) ;

alter table gtfs_rt_feed_entities add constraint gtfs_rt_feed_entities_feed_message_id_entity_id_key
  unique (feed_message_id,entity_id) ;

create index if not exists idx_feed_entities_entity_id
  on gtfs_rt_feed_entities(entity_id);

create index if not exists idx_feed_entities_message_type
  on gtfs_rt_feed_entities(feed_message_id,entity_type);

create unique index if not exists gtfs_rt_feed_entities_PKI
  on gtfs_rt_feed_entities(id);

alter table gtfs_rt_feed_entities
  add constraint gtfs_rt_feed_entities_PKC primary key (id);

create table if not exists gtfs_rt_feed_headers (
  id serial not null
  , feed_message_id integer not null
  , gtfs_realtime_version text default '2.0' not null
  , incrementality text default 'FULL_DATASET' not null
  , timestamp_seconds bigint not null
  , feed_version text
  , created_at timestamp(6) with time zone default now()
) ;

create index if not exists idx_feed_headers_timestamp
  on gtfs_rt_feed_headers(timestamp_seconds);

create unique index if not exists gtfs_rt_feed_headers_PKI
  on gtfs_rt_feed_headers(id);

alter table gtfs_rt_feed_headers
  add constraint gtfs_rt_feed_headers_PKC primary key (id);

create table if not exists gtfs_rt_feed_messages (
  id serial not null
  , feed_type text not null
  , created_at timestamp(6) with time zone default now()
  , file_size integer
  , processed_at timestamp(6) with time zone
) ;

create index if not exists idx_feed_messages_type_created
  on gtfs_rt_feed_messages(feed_type,created_at);

create unique index if not exists gtfs_rt_feed_messages_PKI
  on gtfs_rt_feed_messages(id);

alter table gtfs_rt_feed_messages
  add constraint gtfs_rt_feed_messages_PKC primary key (id);

create table if not exists gtfs_rt_stop_time_updates (
  id serial not null
  , trip_update_id integer not null
  , stop_sequence integer not null
  , stop_id text not null
  , arrival_delay integer
  , arrival_time bigint
  , departure_delay integer
  , departure_time bigint
  , schedule_relationship text default 'SCHEDULED'
  , created_at timestamp(6) with time zone default now()
) ;

alter table gtfs_rt_stop_time_updates add constraint gtfs_rt_stop_time_updates_trip_update_id_stop_sequence_key
  unique (trip_update_id,stop_sequence) ;

create index if not exists idx_stop_time_updates_stop_id
  on gtfs_rt_stop_time_updates(stop_id);

create unique index if not exists gtfs_rt_stop_time_updates_PKI
  on gtfs_rt_stop_time_updates(id);

alter table gtfs_rt_stop_time_updates
  add constraint gtfs_rt_stop_time_updates_PKC primary key (id);

create table if not exists gtfs_rt_trip_descriptors (
  trip_descriptor_id serial not null
  , trip_id text not null
  , start_date text not null
  , schedule_relationship text default 'SCHEDULED' not null
  , route_id text not null
  , direction_id integer not null
  , created_at timestamp(6) with time zone default now()
) ;

alter table gtfs_rt_trip_descriptors add constraint gtfs_rt_trip_descriptors_trip_id_route_id_direction_id_star_key
  unique (trip_id,route_id,direction_id,start_date) ;

create index if not exists idx_trip_descriptors_route_direction
  on gtfs_rt_trip_descriptors(route_id,direction_id);

create index if not exists idx_trip_descriptors_trip_route
  on gtfs_rt_trip_descriptors(trip_id,route_id);

create unique index if not exists gtfs_rt_trip_descriptors_PKI
  on gtfs_rt_trip_descriptors(trip_descriptor_id);

alter table gtfs_rt_trip_descriptors
  add constraint gtfs_rt_trip_descriptors_PKC primary key (trip_descriptor_id);

create table if not exists gtfs_rt_trip_updates (
  trip_update_id serial not null
  , feed_entity_id integer not null
  , trip_descriptor_id integer not null
  , vehicle_descriptor_id integer not null
  , created_at timestamp(6) with time zone default now()
) ;

create index if not exists idx_rt_trip_updates_created_at
  on gtfs_rt_trip_updates(created_at);

create index if not exists idx_trip_updates_feed_entity
  on gtfs_rt_trip_updates(feed_entity_id);

create unique index if not exists gtfs_rt_trip_updates_PKI
  on gtfs_rt_trip_updates(trip_update_id);

alter table gtfs_rt_trip_updates
  add constraint gtfs_rt_trip_updates_PKC primary key (trip_update_id);

create table if not exists gtfs_rt_vehicle_descriptors (
  vehicle_descriptor_id serial not null
  , vehicle_id text not null
  , label text not null
  , created_at timestamp(6) with time zone default now()
) ;

alter table gtfs_rt_vehicle_descriptors add constraint gtfs_rt_vehicle_descriptors_vehicle_id_label_key
  unique (vehicle_id,label) ;

create index if not exists idx_vehicle_descriptors_vehicle_id
  on gtfs_rt_vehicle_descriptors(vehicle_id);

create unique index if not exists gtfs_rt_vehicle_descriptors_PKI
  on gtfs_rt_vehicle_descriptors(vehicle_descriptor_id);

alter table gtfs_rt_vehicle_descriptors
  add constraint gtfs_rt_vehicle_descriptors_PKC primary key (vehicle_descriptor_id);

create table if not exists gtfs_rt_vehicle_positions (
  id serial not null
  , feed_entity_id integer not null
  , trip_descriptor_id integer not null
  , latitude real not null
  , longitude real not null
  , current_stop_sequence integer not null
  , current_status text default 'IN_TRANSIT_TO' not null
  , timestamp_seconds bigint not null
  , stop_id text not null
  , vehicle_descriptor_id integer not null
  , created_at timestamp(6) with time zone default now()
) ;

create index if not exists idx_rt_vehicle_positions_created_at
  on gtfs_rt_vehicle_positions(created_at);

create index if not exists idx_vehicle_positions_feed_entity
  on gtfs_rt_vehicle_positions(feed_entity_id);

create index if not exists idx_vehicle_positions_timestamp
  on gtfs_rt_vehicle_positions(timestamp_seconds);

create index if not exists idx_vehicle_positions_vehicle
  on gtfs_rt_vehicle_positions(vehicle_descriptor_id);

create unique index if not exists gtfs_rt_vehicle_positions_PKI
  on gtfs_rt_vehicle_positions(id);

-- Create PostGIS extension in public schema
CREATE EXTENSION IF NOT EXISTS postgis SCHEMA public;

-- Create regions table in gtfs_static schema
CREATE TABLE IF NOT EXISTS gtfs_static.regions (
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
CREATE INDEX IF NOT EXISTS idx_regions_boundary ON gtfs_static.regions USING GIST(boundary);
CREATE INDEX IF NOT EXISTS idx_regions_name ON gtfs_static.regions(region_name);
CREATE INDEX IF NOT EXISTS idx_regions_type ON gtfs_static.regions(region_type);

alter table gtfs_rt_vehicle_positions
  add constraint gtfs_rt_vehicle_positions_PKC primary key (id);

alter table gtfs_trips_static
  add constraint gtfs_trips_static_FK1 foreign key (direction_id) references gtfs_directions(direction_id);

alter table gtfs_calendar_dates
  add constraint gtfs_calendar_dates_FK1 foreign key (service_id) references gtfs_calendar(service_id);

alter table gtfs_routes
  add constraint gtfs_routes_FK1 foreign key (agency_id) references gtfs_agency(agency_id);

alter table gtfs_stop_times
  add constraint gtfs_stop_times_FK1 foreign key (stop_id) references gtfs_stops(stop_id);

alter table gtfs_stop_times
  add constraint gtfs_stop_times_FK2 foreign key (trip_id) references gtfs_trips_static(trip_id);

alter table gtfs_transfers
  add constraint gtfs_transfers_FK1 foreign key (from_stop_id) references gtfs_stops(stop_id);

alter table gtfs_transfers
  add constraint gtfs_transfers_FK2 foreign key (to_stop_id) references gtfs_stops(stop_id);

alter table gtfs_trips_static
  add constraint gtfs_trips_static_FK2 foreign key (route_id) references gtfs_routes(route_id);

alter table gtfs_trips_static
  add constraint gtfs_trips_static_FK3 foreign key (service_id) references gtfs_calendar(service_id);

alter table gtfs_rt_alert_active_periods
  add constraint gtfs_rt_alert_active_periods_FK1 foreign key (alert_id) references gtfs_rt_alerts(alert_id);

alter table gtfs_rt_alert_text
  add constraint gtfs_rt_alert_text_FK1 foreign key (alert_id) references gtfs_rt_alerts(alert_id);

alter table gtfs_rt_alert_informed_entities
  add constraint gtfs_rt_alert_informed_entities_FK1 foreign key (alert_id) references gtfs_rt_alerts(alert_id);

alter table gtfs_rt_trip_updates
  add constraint gtfs_rt_trip_updates_FK1 foreign key (trip_descriptor_id) references gtfs_rt_trip_descriptors(trip_descriptor_id);

alter table gtfs_rt_trip_updates
  add constraint gtfs_rt_trip_updates_FK2 foreign key (vehicle_descriptor_id) references gtfs_rt_vehicle_descriptors(vehicle_descriptor_id);

alter table gtfs_rt_alerts
  add constraint gtfs_rt_alerts_FK1 foreign key (feed_entity_id) references gtfs_rt_feed_entities(id);

alter table gtfs_rt_feed_entities
  add constraint gtfs_rt_feed_entities_FK1 foreign key (feed_message_id) references gtfs_rt_feed_messages(id);

alter table gtfs_rt_feed_headers
  add constraint gtfs_rt_feed_headers_FK1 foreign key (feed_message_id) references gtfs_rt_feed_messages(id);

alter table gtfs_rt_stop_time_updates
  add constraint gtfs_rt_stop_time_updates_FK1 foreign key (trip_update_id) references gtfs_rt_trip_updates(trip_update_id);

alter table gtfs_rt_trip_updates
  add constraint gtfs_rt_trip_updates_FK3 foreign key (feed_entity_id) references gtfs_rt_feed_entities(id);

alter table gtfs_rt_vehicle_positions
  add constraint gtfs_rt_vehicle_positions_FK1 foreign key (feed_entity_id) references gtfs_rt_feed_entities(id);

alter table gtfs_rt_vehicle_positions
  add constraint gtfs_rt_vehicle_positions_FK2 foreign key (trip_descriptor_id) references gtfs_rt_trip_descriptors(trip_descriptor_id);

alter table gtfs_rt_vehicle_positions
  add constraint gtfs_rt_vehicle_positions_FK3 foreign key (vehicle_descriptor_id) references gtfs_rt_vehicle_descriptors(vehicle_descriptor_id);

-- =============================================================================
-- Helper Functions for Day Offset Handling
-- =============================================================================
-- Purpose: Support GTFS specification for times >= 24:00:00
-- GTFS Spec: "Times greater than 24:00:00 are used for times occurring
--            on the following service day. For example, 25:35:00 is
--            1:35 AM on the day after the service date."
-- =============================================================================

SET search_path TO gtfs_static, public;

-- Calculate actual timestamp for a stop time
CREATE OR REPLACE FUNCTION gtfs_static.get_stop_actual_time(
    service_date DATE,
    time_of_day TIME,
    day_offset INTEGER
)
RETURNS TIMESTAMP
LANGUAGE SQL IMMUTABLE
AS $$
    SELECT (service_date + (day_offset || ' days')::INTERVAL + time_of_day::INTERVAL)::TIMESTAMP;
$$;

COMMENT ON FUNCTION gtfs_static.get_stop_actual_time IS
'Calculate actual timestamp from service date, time, and day offset.
Example: get_stop_actual_time(''2025-10-24'', ''01:35:00'', 1) = ''2025-10-25 01:35:00''';

-- Calculate actual arrival timestamp for a stop_time record
CREATE OR REPLACE FUNCTION gtfs_static.get_actual_arrival_time(
    service_date DATE,
    stop_time_record gtfs_static.gtfs_stop_times
)
RETURNS TIMESTAMP
LANGUAGE SQL IMMUTABLE
AS $$
    SELECT gtfs_static.get_stop_actual_time(
        service_date,
        stop_time_record.arrival_time,
        stop_time_record.arrival_day_offset
    );
$$;

COMMENT ON FUNCTION gtfs_static.get_actual_arrival_time IS
'Calculate actual arrival timestamp for a stop_time record, accounting for day offset.';

RESET search_path;