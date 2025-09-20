-- Active: 1753748166894@@c80eji844tr0op.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com@5432@db5q08f70eh8ap
drop view gtfs_static.gtfs_schedule_view;
create or replace view gtfs_static.gtfs_schedule_view as
select
    routes.route_id
    , routes.route_short_name
    , trips.trip_id
    , trips.trip_headsign
    , trips.direction_id
    , stop_times.stop_sequence
    , stops.stop_id
    , stops.stop_name
    , stop_times.arrival_time
    , case
        when calendar.monday = 1 
            or calendar.tuesday = 1
            or calendar.wednesday = 1
            or calendar.thursday = 1
            or calendar.friday = 1
            then 1
        else 0
      end as week_day
    , calendar.saturday
    , calendar.sunday
from gtfs_static.gtfs_routes routes
inner join gtfs_static.gtfs_trips_static trips
    on routes.route_id = trips.route_id
inner join gtfs_static.gtfs_stop_times stop_times
    on trips.trip_id = stop_times.trip_id
inner join gtfs_static.gtfs_stops stops
    on stop_times.stop_id = stops.stop_id
inner join gtfs_static.gtfs_calendar calendar
    on trips.service_id = calendar.service_id
order by trip_id, stop_sequence;

drop MATERIALIZED VIEW if exists gtfs_realtime.gtfs_rt_stop_time_updates_mv;
create MATERIALIZED VIEW gtfs_realtime.gtfs_rt_stop_time_updates_mv as
select distinct on (trip_id, stop_sequence, start_date)
     stu.id
    , td.route_id
    , td.trip_id
    , stu.stop_id
    , r.route_short_name
    , t.trip_headsign
    , t.direction_id
    , s.stop_name
    , st.arrival_time
    , stu.stop_sequence
    , td.start_date
    , to_timestamp(stu.arrival_time) as actual_arrival_time
    , stu.arrival_delay
    , to_timestamp(fh.timestamp_seconds) as update_time
from gtfs_realtime.gtfs_rt_stop_time_updates stu
inner join gtfs_realtime.gtfs_rt_trip_updates tu
    on stu.trip_update_id = tu.trip_update_id
inner join gtfs_realtime.gtfs_rt_trip_descriptors td
    on tu.trip_descriptor_id = td.trip_descriptor_id
inner join gtfs_realtime.gtfs_rt_feed_entities fe
    on tu.feed_entity_id = fe.id
inner join gtfs_realtime.gtfs_rt_feed_messages fm
    on fe.feed_message_id = fm.id
inner join gtfs_realtime.gtfs_rt_feed_headers fh
    on fm.id = fh.feed_message_id
inner join gtfs_static.gtfs_routes r
    on r.route_id = td.route_id
inner join gtfs_static.gtfs_trips_static t
    on t.trip_id = td.trip_id
inner join gtfs_static.gtfs_stops s
    on s.stop_id = stu.stop_id
inner join gtfs_static.gtfs_stop_times st
    on st.trip_id = td.trip_id and st.stop_id = stu.stop_id
order by start_date, trip_id, stop_sequence, update_time desc;

CREATE OR REPLACE PROCEDURE gtfs_realtime.refresh_gtfs_views()
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW gtfs_realtime.gtfs_rt_stop_time_updates_mv;

    RAISE NOTICE 'Materialized views refreshed at %', NOW();
END;
$$;

call gtfs_realtime.refresh_gtfs_views();