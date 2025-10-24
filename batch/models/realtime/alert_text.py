from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from batch.config.database_connector import Base


class GTFSRTAlertText(Base):
    __tablename__ = "gtfs_rt_alert_text"
    __table_args__ = {"schema": "gtfs_realtime"}

    alert_url_id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_alerts.alert_id"), nullable=False)
    text_type = Column(Text, nullable=False)
    text = Column(Text)
    language = Column(Text)

    alert = relationship("GTFSRTAlert", back_populates="alert_texts")
