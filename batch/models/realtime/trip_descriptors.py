from sqlalchemy import Column, Integer, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from batch.config.database_connector import Base


class GTFSRTTripDescriptor(Base):
    __tablename__ = "gtfs_rt_trip_descriptors"
    __table_args__ = {"schema": "gtfs_realtime"}

    trip_descriptor_id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(Text, nullable=False)
    start_date = Column(Text, nullable=False)
    schedule_relationship = Column(Text, default='SCHEDULED', nullable=False)
    route_id = Column(Text, nullable=False)
    direction_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip_updates = relationship("GTFSRTTripUpdate", back_populates="trip_descriptor")
    vehicle_positions = relationship("GTFSRTVehiclePosition", back_populates="trip_descriptor")
