from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from batch.config.database_connector import Base


class GTFSRTAlert(Base):
    __tablename__ = "gtfs_rt_alerts"
    __table_args__ = {"schema": "gtfs_realtime"}

    alert_id = Column(Integer, primary_key=True, autoincrement=True)
    feed_entity_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_feed_entities.id"), nullable=False)
    cause = Column(Text, nullable=False)
    effect = Column(Text, nullable=False)
    severity_level = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    feed_entity = relationship("GTFSRTFeedEntity", back_populates="alert")
    alert_texts = relationship("GTFSRTAlertText", back_populates="alert")
    active_periods = relationship("GTFSRTAlertActivePeriod", back_populates="alert")
    informed_entities = relationship("GTFSRTAlertInformedEntity", back_populates="alert")
