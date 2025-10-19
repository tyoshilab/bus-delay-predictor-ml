from sqlalchemy.orm import Session
from batch.models.realtime.trip_updates import GTFSRTTripUpdate, GTFSRTStopTimeUpdate


class TripUpdatesService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create_trip_update(self, entity_id: int, trip_update, trip_desc_id: int, vehicle_desc_id: int) -> GTFSRTTripUpdate:
        trip_update_record = GTFSRTTripUpdate(
            feed_entity_id=entity_id,
            trip_descriptor_id=trip_desc_id,
            vehicle_descriptor_id=vehicle_desc_id
        )
        self.db.add(trip_update_record)
        self.db.commit()
        self.db.refresh(trip_update_record)
        for stu in trip_update.stop_time_update:
            self.create_stop_time_update(trip_update_record.trip_update_id, stu)
        return trip_update_record

    def create_stop_time_update(self, trip_update_id: int, stu) -> GTFSRTStopTimeUpdate:
        arrival_delay = None
        arrival_time = None
        departure_delay = None
        departure_time = None
        if stu.HasField('arrival'):
            arrival = stu.arrival
            arrival_delay = arrival.delay if arrival.HasField('delay') else None
            arrival_time = arrival.time if arrival.HasField('time') else None
        if stu.HasField('departure'):
            departure = stu.departure
            departure_delay = departure.delay if departure.HasField('delay') else None
            departure_time = departure.time if departure.HasField('time') else None
        stop_time_update = GTFSRTStopTimeUpdate(
            trip_update_id=trip_update_id,
            stop_sequence=stu.stop_sequence if stu.HasField('stop_sequence') else None,
            stop_id=stu.stop_id if stu.HasField('stop_id') else None,
            arrival_delay=arrival_delay,
            arrival_time=arrival_time,
            departure_delay=departure_delay,
            departure_time=departure_time,
            schedule_relationship=self._get_stop_schedule_relationship(stu.schedule_relationship) if stu.HasField('schedule_relationship') else 'SCHEDULED'
        )
        self.db.add(stop_time_update)
        self.db.commit()
        self.db.refresh(stop_time_update)
        return stop_time_update

    def _get_stop_schedule_relationship(self, relationship) -> str:
        mapping = {0: 'SCHEDULED', 1: 'SKIPPED', 2: 'NO_DATA', 3: 'UNSCHEDULED'}
        return mapping.get(relationship, 'SCHEDULED')
