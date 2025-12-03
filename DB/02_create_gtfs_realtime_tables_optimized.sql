-- Project Name : noname
-- Date/Time    : 2025/07/29 16:46:40
-- Author       : loveu
-- RDBMS Type   : PostgreSQL
-- Application  : A5:SQL Mk-2
--
-- PERFORMANCE OPTIMIZATION:
-- All non-primary key indexes have been temporarily commented out
-- to improve bulk insert performance during --all-timestamps operations.
-- Uncomment indexes after bulk data loading is complete.

create schema if not exists gtfs_realtime;
SET search_path TO gtfs_realtime, public;

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

create unique index if not exists gtfs_rt_feed_headers_PKI
  on gtfs_rt_feed_headers(id);

CREATE INDEX IF NOT EXISTS idx_rt_feed_order
  ON gtfs_realtime.gtfs_rt_feed_headers (timestamp_seconds DESC);

alter table gtfs_rt_feed_headers
  add constraint gtfs_rt_feed_headers_PKC primary key (id);

create table if not exists gtfs_rt_feed_messages (
  id serial not null
  , feed_type text not null
  , created_at timestamp(6) with time zone default now()
  , file_size integer
  , processed_at timestamp(6) with time zone
) ;

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

create unique index if not exists gtfs_rt_stop_time_updates_PKI
  on gtfs_rt_stop_time_updates(id);

CREATE INDEX IF NOT EXISTS idx_rt_trip_order
  ON gtfs_realtime.gtfs_rt_stop_time_updates (trip_update_id, stop_sequence);

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

create unique index if not exists gtfs_rt_vehicle_positions_PKI
  on gtfs_rt_vehicle_positions(id);

CREATE INDEX if not exists idx_vp_timestamp_seconds 
ON gtfs_realtime.gtfs_rt_vehicle_positions (timestamp_seconds);

alter table gtfs_rt_vehicle_positions
  add constraint gtfs_rt_vehicle_positions_PKC primary key (id);

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

comment on table gtfs_rt_alert_text is 'gtfs_rt_alert_text';
comment on column gtfs_rt_alert_text.alert_url_id is 'alert_url_id';
comment on column gtfs_rt_alert_text.alert_id is 'alert_id';
comment on column gtfs_rt_alert_text.text_type is 'text_type';
comment on column gtfs_rt_alert_text.text is 'text';
comment on column gtfs_rt_alert_text.language is 'language';

comment on table gtfs_rt_alert_active_periods is 'gtfs_rt_alert_active_periods';
comment on column gtfs_rt_alert_active_periods.alert_period_id is 'alert_period_id';
comment on column gtfs_rt_alert_active_periods.alert_id is 'alert_id';
comment on column gtfs_rt_alert_active_periods.period_time is 'period_time';

comment on table gtfs_rt_alert_informed_entities is 'gtfs_rt_alert_informed_entities';
comment on column gtfs_rt_alert_informed_entities.alert_informed_id is 'alert_informed_id';
comment on column gtfs_rt_alert_informed_entities.alert_id is 'alert_id';
comment on column gtfs_rt_alert_informed_entities.agency_id is 'agency_id';
comment on column gtfs_rt_alert_informed_entities.route_id is 'route_id';
comment on column gtfs_rt_alert_informed_entities.route_type is 'route_type';
comment on column gtfs_rt_alert_informed_entities.stop_id is 'stop_id';

comment on table gtfs_rt_alerts is 'gtfs_rt_alerts';
comment on column gtfs_rt_alerts.alert_id is 'alert_id';
comment on column gtfs_rt_alerts.feed_entity_id is 'feed_entity_id';
comment on column gtfs_rt_alerts.cause is 'cause';
comment on column gtfs_rt_alerts.effect is 'effect';
comment on column gtfs_rt_alerts.severity_level is 'severity_level';
comment on column gtfs_rt_alerts.created_at is 'created_at';

comment on table gtfs_rt_feed_entities is 'gtfs_rt_feed_entities';
comment on column gtfs_rt_feed_entities.id is 'id';
comment on column gtfs_rt_feed_entities.feed_message_id is 'feed_message_id';
comment on column gtfs_rt_feed_entities.entity_id is 'entity_id';
comment on column gtfs_rt_feed_entities.is_deleted is 'is_deleted';
comment on column gtfs_rt_feed_entities.entity_type is 'entity_type';
comment on column gtfs_rt_feed_entities.created_at is 'created_at';

comment on table gtfs_rt_feed_headers is 'gtfs_rt_feed_headers';
comment on column gtfs_rt_feed_headers.id is 'id';
comment on column gtfs_rt_feed_headers.feed_message_id is 'feed_message_id';
comment on column gtfs_rt_feed_headers.gtfs_realtime_version is 'gtfs_realtime_version';
comment on column gtfs_rt_feed_headers.incrementality is 'incrementality';
comment on column gtfs_rt_feed_headers.timestamp_seconds is 'timestamp_seconds';
comment on column gtfs_rt_feed_headers.feed_version is 'feed_version';
comment on column gtfs_rt_feed_headers.created_at is 'created_at';

comment on table gtfs_rt_feed_messages is 'gtfs_rt_feed_messages';
comment on column gtfs_rt_feed_messages.id is 'id';
comment on column gtfs_rt_feed_messages.feed_type is 'feed_type';
comment on column gtfs_rt_feed_messages.created_at is 'created_at';
comment on column gtfs_rt_feed_messages.file_size is 'file_size';
comment on column gtfs_rt_feed_messages.processed_at is 'processed_at';

comment on table gtfs_rt_stop_time_updates is 'gtfs_rt_stop_time_updates';
comment on column gtfs_rt_stop_time_updates.id is 'id';
comment on column gtfs_rt_stop_time_updates.trip_update_id is 'trip_update_id';
comment on column gtfs_rt_stop_time_updates.stop_sequence is 'stop_sequence';
comment on column gtfs_rt_stop_time_updates.stop_id is 'stop_id';
comment on column gtfs_rt_stop_time_updates.arrival_delay is 'arrival_delay';
comment on column gtfs_rt_stop_time_updates.arrival_time is 'arrival_time';
comment on column gtfs_rt_stop_time_updates.departure_delay is 'departure_delay';
comment on column gtfs_rt_stop_time_updates.departure_time is 'departure_time';
comment on column gtfs_rt_stop_time_updates.schedule_relationship is 'schedule_relationship';
comment on column gtfs_rt_stop_time_updates.created_at is 'created_at';

comment on table gtfs_rt_trip_descriptors is 'gtfs_rt_trip_descriptors';
comment on column gtfs_rt_trip_descriptors.trip_descriptor_id is 'trip_descriptor_id';
comment on column gtfs_rt_trip_descriptors.trip_id is 'trip_id';
comment on column gtfs_rt_trip_descriptors.start_date is 'start_date';
comment on column gtfs_rt_trip_descriptors.schedule_relationship is 'schedule_relationship';
comment on column gtfs_rt_trip_descriptors.route_id is 'route_id';
comment on column gtfs_rt_trip_descriptors.direction_id is 'direction_id';
comment on column gtfs_rt_trip_descriptors.created_at is 'created_at';

comment on table gtfs_rt_trip_updates is 'gtfs_rt_trip_updates';
comment on column gtfs_rt_trip_updates.trip_update_id is 'trip_update_id';
comment on column gtfs_rt_trip_updates.feed_entity_id is 'feed_entity_id';
comment on column gtfs_rt_trip_updates.trip_descriptor_id is 'trip_descriptor_id';
comment on column gtfs_rt_trip_updates.vehicle_descriptor_id is 'vehicle_descriptor_id';
comment on column gtfs_rt_trip_updates.created_at is 'created_at';

comment on table gtfs_rt_vehicle_descriptors is 'gtfs_rt_vehicle_descriptors';
comment on column gtfs_rt_vehicle_descriptors.vehicle_descriptor_id is 'vehicle_descriptor_id';
comment on column gtfs_rt_vehicle_descriptors.vehicle_id is 'vehicle_id';
comment on column gtfs_rt_vehicle_descriptors.label is 'label';
comment on column gtfs_rt_vehicle_descriptors.created_at is 'created_at';

comment on table gtfs_rt_vehicle_positions is 'gtfs_rt_vehicle_positions';
comment on column gtfs_rt_vehicle_positions.id is 'id';
comment on column gtfs_rt_vehicle_positions.feed_entity_id is 'feed_entity_id';
comment on column gtfs_rt_vehicle_positions.trip_descriptor_id is 'trip_descriptor_id';
comment on column gtfs_rt_vehicle_positions.latitude is 'latitude';
comment on column gtfs_rt_vehicle_positions.longitude is 'longitude';
comment on column gtfs_rt_vehicle_positions.current_stop_sequence is 'current_stop_sequence';
comment on column gtfs_rt_vehicle_positions.current_status is 'current_status';
comment on column gtfs_rt_vehicle_positions.timestamp_seconds is 'timestamp_seconds';
comment on column gtfs_rt_vehicle_positions.stop_id is 'stop_id';
comment on column gtfs_rt_vehicle_positions.vehicle_descriptor_id is 'vehicle_descriptor_id';
comment on column gtfs_rt_vehicle_positions.created_at is 'created_at';

RESET search_path;
