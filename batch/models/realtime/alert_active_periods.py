from sqlalchemy import Column, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from batch.config.database_connector import Base


class GTFSRTAlertActivePeriod(Base):
    __tablename__ = "gtfs_rt_alert_active_periods"
    __table_args__ = {"schema": "gtfs_realtime"}

    alert_period_id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_alerts.alert_id"), nullable=False)
    period_time = Column(BigInteger)

    alert = relationship("GTFSRTAlert", back_populates="active_periods")
