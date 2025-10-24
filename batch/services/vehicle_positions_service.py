from sqlalchemy.orm import Session
from batch.models.realtime.trip_descriptors import GTFSRTTripDescriptor
from batch.models.realtime.vehicle_descriptors import GTFSRTVehicleDescriptor
from batch.models.realtime.vehicle_positions import GTFSRTVehiclePosition


class VehiclePositionsService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create_or_get_trip_descriptor(self, trip_desc) -> GTFSRTTripDescriptor:
        trip_id = trip_desc.trip_id if trip_desc.HasField('trip_id') else 'UNKNOWN'
        route_id = trip_desc.route_id if trip_desc.HasField('route_id') else 'UNKNOWN'
        direction_id = trip_desc.direction_id if trip_desc.HasField('direction_id') else 0
        start_date = trip_desc.start_date if trip_desc.HasField('start_date') else '20250101'
        existing = self.db.query(GTFSRTTripDescriptor).filter(
            GTFSRTTripDescriptor.trip_id == trip_id,
            GTFSRTTripDescriptor.route_id == route_id,
            GTFSRTTripDescriptor.direction_id == direction_id,
            GTFSRTTripDescriptor.start_date == start_date
        ).first()
        if existing:
            return existing
        trip_descriptor = GTFSRTTripDescriptor(
            trip_id=trip_id,
            route_id=route_id,
            direction_id=direction_id,
            start_date=start_date,
            schedule_relationship=self._get_schedule_relationship(trip_desc.schedule_relationship) if trip_desc.HasField('schedule_relationship') else 'SCHEDULED'
        )
        self.db.add(trip_descriptor)
        self.db.commit()
        self.db.refresh(trip_descriptor)
        return trip_descriptor

    def create_or_get_vehicle_descriptor(self, vehicle_desc) -> GTFSRTVehicleDescriptor:
        vehicle_id = vehicle_desc.id if vehicle_desc.HasField('id') else 'UNKNOWN'
        label = vehicle_desc.label if vehicle_desc.HasField('label') else 'UNKNOWN'
        existing = self.db.query(GTFSRTVehicleDescriptor).filter(
            GTFSRTVehicleDescriptor.vehicle_id == vehicle_id,
            GTFSRTVehicleDescriptor.label == label
        ).first()
        if existing:
            return existing
        vehicle_descriptor = GTFSRTVehicleDescriptor(
            vehicle_id=vehicle_id,
            label=label
        )
        self.db.add(vehicle_descriptor)
        self.db.commit()
        self.db.refresh(vehicle_descriptor)
        return vehicle_descriptor

    def create_vehicle_position(self, entity_id: int, vehicle_pos, trip_desc_id: int, vehicle_desc_id: int) -> GTFSRTVehiclePosition:
        vehicle_position = GTFSRTVehiclePosition(
            feed_entity_id=entity_id,
            trip_descriptor_id=trip_desc_id,
            latitude=vehicle_pos.position.latitude if vehicle_pos.HasField('position') and vehicle_pos.position.HasField('latitude') else None,
            longitude=vehicle_pos.position.longitude if vehicle_pos.HasField('position') and vehicle_pos.position.HasField('longitude') else None,
            current_stop_sequence=vehicle_pos.current_stop_sequence if vehicle_pos.HasField('current_stop_sequence') else None,
            current_status=self._get_vehicle_stop_status(vehicle_pos.current_status) if vehicle_pos.HasField('current_status') else 'IN_TRANSIT_TO',
            timestamp_seconds=vehicle_pos.timestamp if vehicle_pos.HasField('timestamp') else None,
            stop_id=vehicle_pos.stop_id if vehicle_pos.HasField('stop_id') else None,
            vehicle_descriptor_id=vehicle_desc_id,
        )
        self.db.add(vehicle_position)
        self.db.commit()
        self.db.refresh(vehicle_position)
        return vehicle_position

    def _get_schedule_relationship(self, relationship) -> str:
        mapping = {0: 'SCHEDULED', 1: 'ADDED', 2: 'UNSCHEDULED', 3: 'CANCELED', 5: 'REPLACEMENT', 6: 'DUPLICATED', 7: 'DELETED', 8: 'NEW'}
        return mapping.get(relationship, 'SCHEDULED')

    def _get_vehicle_stop_status(self, status) -> str:
        mapping = {0: 'INCOMING_AT', 1: 'STOPPED_AT', 2: 'IN_TRANSIT_TO'}
        return mapping.get(status, 'IN_TRANSIT_TO')
