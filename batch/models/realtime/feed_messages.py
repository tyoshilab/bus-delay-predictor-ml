from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from batch.config.database_connector import Base


class GTFSRTFeedMessage(Base):
    __tablename__ = "gtfs_rt_feed_messages"
    __table_args__ = {"schema": "gtfs_realtime"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_type = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    file_size = Column(Integer)
    processed_at = Column(DateTime(timezone=True))

    header = relationship("GTFSRTFeedHeader", back_populates="feed_message", uselist=False)
    entities = relationship("GTFSRTFeedEntity", back_populates="feed_message")


class GTFSRTFeedHeader(Base):
    __tablename__ = "gtfs_rt_feed_headers"
    __table_args__ = {"schema": "gtfs_realtime"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_message_id = Column(Integer, ForeignKey("gtfs_realtime.gtfs_rt_feed_messages.id"), nullable=False)
    gtfs_realtime_version = Column(Text, default='2.0', nullable=False)
    incrementality = Column(Text, default='FULL_DATASET', nullable=False)
    timestamp_seconds = Column(BigInteger, nullable=True)
    feed_version = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    feed_message = relationship("GTFSRTFeedMessage", back_populates="header")
