from sqlalchemy import Column, Integer, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from batch.config.database_connector import Base


class GTFSRTVehicleDescriptor(Base):
    __tablename__ = "gtfs_rt_vehicle_descriptors"
    __table_args__ = {"schema": "gtfs_realtime"}

    vehicle_descriptor_id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Text, nullable=False)
    label = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip_updates = relationship("GTFSRTTripUpdate", back_populates="vehicle_descriptor")
    vehicle_positions = relationship("GTFSRTVehiclePosition", back_populates="vehicle_descriptor")
