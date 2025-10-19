from sqlalchemy import Column, Integer, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from batch.config.database_connector import Base


class GTFSRTFeedEntity(Base):
    __tablename__ = "gtfs_rt_feed_entities"
    __table_args__ = {"schema": "gtfs_realtime"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_message_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_feed_messages.id"), nullable=False)
    entity_id = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False)
    entity_type = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    feed_message = relationship("GTFSRTFeedMessage", back_populates="entities")
    trip_update = relationship("GTFSRTTripUpdate", back_populates="feed_entity", uselist=False)
    vehicle_position = relationship("GTFSRTVehiclePosition", back_populates="feed_entity", uselist=False)
    alert = relationship("GTFSRTAlert", back_populates="feed_entity", uselist=False)
