from sqlalchemy.orm import Session
from batch.models.realtime.feed_messages import GTFSRTFeedMessage, GTFSRTFeedHeader
from batch.models.realtime.feed_entities import GTFSRTFeedEntity
import os
from google.protobuf.json_format import MessageToJson


class FeedMessageService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create_feed_message(self, feed_type: str, file_size: int) -> GTFSRTFeedMessage:
        feed_message = GTFSRTFeedMessage(
            feed_type=feed_type,
            file_size=file_size
        )
        self.db.add(feed_message)
        self.db.commit()
        self.db.refresh(feed_message)
        return feed_message

    def create_feed_header(self, feed_message_id: int, header) -> GTFSRTFeedHeader:
        header_record = GTFSRTFeedHeader(
            feed_message_id=feed_message_id,
            gtfs_realtime_version=getattr(header, 'gtfs_realtime_version', '2.0'),
            incrementality='FULL_DATASET' if getattr(header, 'incrementality', 0) == 0 else 'DIFFERENTIAL',
            timestamp_seconds=getattr(header, 'timestamp', None),
            feed_version=getattr(header, 'feed_version', None)
        )
        self.db.add(header_record)
        self.db.commit()
        self.db.refresh(header_record)
        return header_record

    def create_feed_entity(self, feed_msg_id: int, entity) -> GTFSRTFeedEntity:
        entity_type = self._get_entity_type(entity)
        existing = self.db.query(GTFSRTFeedEntity).filter(
            GTFSRTFeedEntity.feed_message_id == feed_msg_id,
            GTFSRTFeedEntity.entity_id == entity.id
        ).first()
        if existing:
            return existing
        feed_entity = GTFSRTFeedEntity(
            feed_message_id=feed_msg_id,
            entity_id=entity.id,
            is_deleted=getattr(entity, 'is_deleted', False),
            entity_type=entity_type
        )
        self.db.add(feed_entity)
        self.db.commit()
        self.db.refresh(feed_entity)
        return feed_entity

    def _get_entity_type(self, entity) -> str:
        if entity.HasField('trip_update'):
            return 'trip_update'
        elif entity.HasField('vehicle'):
            return 'vehicle_position'
        elif entity.HasField('alert'):
            return 'alert'
        return 'unknown'

    def load_and_parse_feed_message(self, pb_file_path: str):
        if not os.path.exists(pb_file_path):
            raise FileNotFoundError(f"File not found: {pb_file_path}")
        import batch.controller.gtfs_realtime_pb2 as gtfs_realtime_pb2
        with open(pb_file_path, 'rb') as f:
            data = f.read()
        feed_message = gtfs_realtime_pb2.FeedMessage()
        feed_message.ParseFromString(data)
        return feed_message, data

    def convert_to_json(self, feed_message, pb_file_path: str, feed_type: str) -> str:
        feed_message_json = MessageToJson(feed_message, preserving_proto_field_name=True)
        base_filename = os.path.splitext(os.path.basename(pb_file_path))[0]
        json_filename = f"{base_filename}_{feed_type}.json"
        json_filepath = os.path.join(os.path.dirname(pb_file_path), json_filename)
        with open(json_filepath, 'w', encoding='utf-8') as json_file:
            json_file.write(feed_message_json)
        return json_filepath

    def print_feed_info(self, feed_message, feed_type: str):
        print(f"Loading {feed_type} feed: {len(feed_message.entity)} entities")
        print(f"Feed header - GTFS version: {feed_message.header.gtfs_realtime_version}")
        print(f"Feed header - Timestamp: {feed_message.header.timestamp}")
        print(f"Feed header - Incrementality: {feed_message.header.incrementality}")
