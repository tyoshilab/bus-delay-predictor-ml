from sqlalchemy import Column, Integer, ForeignKey, DateTime, BigInteger, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from batch.config.database_connector import Base


class GTFSRTTripUpdate(Base):
    __tablename__ = "gtfs_rt_trip_updates"
    __table_args__ = {"schema": "gtfs_realtime"}

    trip_update_id = Column(Integer, primary_key=True, autoincrement=True)
    feed_entity_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_feed_entities.id"), nullable=False)
    trip_descriptor_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_trip_descriptors.trip_descriptor_id"), nullable=False)
    vehicle_descriptor_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_vehicle_descriptors.vehicle_descriptor_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    feed_entity = relationship("GTFSRTFeedEntity", back_populates="trip_update")
    trip_descriptor = relationship("GTFSRTTripDescriptor", back_populates="trip_updates")
    vehicle_descriptor = relationship("GTFSRTVehicleDescriptor", back_populates="trip_updates")
    stop_time_updates = relationship("GTFSRTStopTimeUpdate", back_populates="trip_update")


class GTFSRTStopTimeUpdate(Base):
    __tablename__ = "gtfs_rt_stop_time_updates"
    __table_args__ = {"schema": "gtfs_realtime"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_update_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_trip_updates.trip_update_id"), nullable=False)
    stop_sequence = Column(Integer, nullable=True)
    stop_id = Column(Text, nullable=True)
    arrival_delay = Column(Integer)
    arrival_time = Column(BigInteger)
    departure_delay = Column(Integer)
    departure_time = Column(BigInteger)
    schedule_relationship = Column(Text, default='SCHEDULED')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip_update = relationship("GTFSRTTripUpdate", back_populates="stop_time_updates")
