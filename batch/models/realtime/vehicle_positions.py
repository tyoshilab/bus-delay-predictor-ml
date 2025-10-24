from sqlalchemy import Column, Integer, ForeignKey, Float, DateTime, BigInteger, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from batch.config.database_connector import Base


class GTFSRTVehiclePosition(Base):
    __tablename__ = "gtfs_rt_vehicle_positions"
    __table_args__ = {"schema": "gtfs_realtime"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_entity_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_feed_entities.id"), nullable=False)
    trip_descriptor_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_trip_descriptors.trip_descriptor_id"), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    current_stop_sequence = Column(Integer, nullable=True)
    current_status = Column(Text, default='IN_TRANSIT_TO', nullable=True)
    timestamp_seconds = Column(BigInteger, nullable=True)
    stop_id = Column(Text, nullable=True)
    vehicle_descriptor_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_vehicle_descriptors.vehicle_descriptor_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    feed_entity = relationship("GTFSRTFeedEntity", back_populates="vehicle_position")
    trip_descriptor = relationship("GTFSRTTripDescriptor", back_populates="vehicle_positions")
    vehicle_descriptor = relationship("GTFSRTVehicleDescriptor", back_populates="vehicle_positions")
