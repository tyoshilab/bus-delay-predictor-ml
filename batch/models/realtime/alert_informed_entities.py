from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from batch.config.database_connector import Base


class GTFSRTAlertInformedEntity(Base):
    __tablename__ = "gtfs_rt_alert_informed_entities"
    __table_args__ = {"schema": "gtfs_realtime"}

    alert_informed_id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_alerts.alert_id"), nullable=False)
    agency_id = Column(Text)
    route_id = Column(Text)
    route_type = Column(Integer)
    stop_id = Column(Text)

    alert = relationship("GTFSRTAlert", back_populates="informed_entities")
