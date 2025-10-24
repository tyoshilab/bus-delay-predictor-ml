#!/usr/bin/env python3
"""
Load GTFS Realtime protobuf data into PostgreSQL database.
Processes all 3 TransLink feed types: trip_updates, vehicle_positions, alerts
"""

import sys
import os

# Add paths for imports
controller_dir = os.path.dirname(os.path.abspath(__file__))
batch_dir = os.path.dirname(controller_dir)
project_root = os.path.dirname(batch_dir)

sys.path.insert(0, project_root)
sys.path.insert(0, controller_dir)  # Add controller dir for direct gtfs_realtime_pb2 import

try:
    import gtfs_realtime_pb2
except ImportError as e:
    print(f"Error: gtfs_realtime_pb2.py not found. Please generate it from gtfs-realtime.proto")
    print(f"Controller dir: {controller_dir}")
    print(f"Project root: {project_root}")
    print(f"sys.path: {sys.path[:5]}")
    print(f"Files in controller_dir: {os.listdir(controller_dir)[:10]}")
    print(f"Import error details: {e}")
    sys.exit(1)

# Import database configuration
from batch.config.database_connector import DatabaseConnector

# Import ORM service classes
from batch.services import (
    FeedMessageService,
    VehiclePositionsService,
    TripUpdatesService,
    AlertsService
)


class GTFSRealtimeLoader:
    def __init__(self):
        self.db_connector = None
        self.db_session = None
        # Initialize service instances (will be set after DB connection)
        self.feed_message_service = None
        self.vehicle_positions_service = None
        self.trip_updates_service = None
        self.alerts_service = None

    def connect_db(self):
        """Connect to PostgreSQL database using SQLAlchemy ORM."""
        try:
            self.db_connector = DatabaseConnector()
            self.db_session = self.db_connector.get_session()

            # Initialize ORM service instances
            self.feed_message_service = FeedMessageService(self.db_session)
            self.vehicle_positions_service = VehiclePositionsService(self.db_session)
            self.trip_updates_service = TripUpdatesService(self.db_session)
            self.alerts_service = AlertsService(self.db_session)

            print("Connected to database successfully using ORM")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            sys.exit(1)

    def close_db(self):
        """Close database session."""
        if self.db_session:
            self.db_session.close()

    def load_feed_message(self, pb_file_path, feed_type):
        """Load a protobuf feed file into the database."""
        try:
            # Read and parse protobuf
            with open(pb_file_path, 'rb') as f:
                data = f.read()
            
            return self.load_feed_data(data, feed_type)
            
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return None
        except Exception as e:
            print(f"Error loading {pb_file_path}: {e}")
            if self.db_session:
                self.db_session.rollback()
            import traceback
            traceback.print_exc()
            return None

    def load_feed_data(self, data, feed_type):
        """Load protobuf data (bytes) into the database."""
        try:
            feed_message = gtfs_realtime_pb2.FeedMessage()
            feed_message.ParseFromString(data)
            
            print(f"Loading {feed_type} feed: {len(feed_message.entity)} entities")
            
            # Insert feed message using ORM service
            feed_msg_record = self.feed_message_service.create_feed_message(feed_type, len(data))
            
            # Insert header using ORM service
            header_record = self.feed_message_service.create_feed_header(feed_msg_record.id, feed_message.header)
            
            # Process entities
            entity_count = 0
            for entity in feed_message.entity:
                self.insert_feed_entity(feed_msg_record.id, entity)
                entity_count += 1
                
                if entity_count % 100 == 0:
                    print(f"Processed {entity_count} entities...")
            
            print(f"Successfully loaded {entity_count} entities for {feed_type}")
            return feed_msg_record.id
            
        except Exception as e:
            print(f"Error loading protobuf data: {e}")
            if self.db_session:
                self.db_session.rollback()
            import traceback
            traceback.print_exc()
            return None


    def insert_feed_entity(self, feed_msg_id, entity):
        """Insert feed entity and its specific data."""
        # Insert base entity using ORM feed service
        entity_record = self.feed_message_service.create_feed_entity(feed_msg_id, entity)

        # Process specific entity types using appropriate ORM services
        if entity.HasField('trip_update'):
            self.insert_trip_update(entity_record.id, entity.trip_update)
        elif entity.HasField('vehicle'):
            self.insert_vehicle_position(entity_record.id, entity.vehicle)
        elif entity.HasField('alert'):
            self.insert_alert(entity_record.id, entity.alert)


    def insert_trip_update(self, entity_id: int, trip_update):
        """Insert trip update data using ORM."""
        # Create or get descriptors
        trip_desc = self.vehicle_positions_service.create_or_get_trip_descriptor(trip_update.trip)
        vehicle_desc = self.vehicle_positions_service.create_or_get_vehicle_descriptor(trip_update.vehicle)

        # Create trip update
        self.trip_updates_service.create_trip_update(entity_id, trip_update, trip_desc.trip_descriptor_id, vehicle_desc.vehicle_descriptor_id)
    
    
    def insert_vehicle_position(self, entity_id: int, vehicle_pos):
        """Insert vehicle position data using ORM."""
        # Create or get descriptors
        trip_desc = self.vehicle_positions_service.create_or_get_trip_descriptor(vehicle_pos.trip)
        vehicle_desc = self.vehicle_positions_service.create_or_get_vehicle_descriptor(vehicle_pos.vehicle)

        # Create vehicle position
        self.vehicle_positions_service.create_vehicle_position(entity_id, vehicle_pos, trip_desc.trip_descriptor_id, vehicle_desc.vehicle_descriptor_id)


    def insert_alert(self, entity_id: int, alert):
        """Insert alert data using ORM."""
        # Create alert record
        alert_entity = self.alerts_service.create_alert(entity_id, alert)

        # Create alert active periods
        for active_period in alert.active_period:
            self.alerts_service.create_alert_active_period(alert_entity.alert_id, active_period)
        # Create alert informed entities
        for informed_entity in alert.informed_entity:
            self.alerts_service.create_alert_informed_entity(alert_entity.alert_id, informed_entity)
        # Create alert text
        alert_header = ['url', 'header_text', 'description_text', 'cause_detail', 'effect_detail']
        for text_type in alert_header:
            if hasattr(alert, text_type) and getattr(alert, text_type):
                for alert_text in getattr(alert, text_type).translation:
                    self.alerts_service.create_alert_text(alert_entity.alert_id, alert_text, text_type)


def main():
    """Main function."""
    base_dir = os.path.dirname(__file__)
    
    # Define the files to load
    pb_files = [
        ('translink_gtfsrt.pb', 'trip_updates'),
        ('translink_gtfsposition.pb', 'vehicle_positions'),
        ('translink_gtfsalerts.pb', 'alerts')
    ]
    
    loader = GTFSRealtimeLoader()
    loader.connect_db()
    
    try:
        for filename, feed_type in pb_files:
            pb_file_path = os.path.join(base_dir, filename)
            print(f"\n{'='*60}")
            print(f"Loading {feed_type} from {filename}")
            print(f"{'='*60}")
            
            feed_msg_id = loader.load_feed_message(pb_file_path, feed_type)
            if feed_msg_id:
                print(f"Successfully loaded feed message ID: {feed_msg_id}")
            else:
                print(f"Failed to load {filename}")
                
        print(f"\n{'='*60}")
        print("Data loading completed using ORM!")
        print(f"{'='*60}")
                
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loader.close_db()

if __name__ == "__main__":
    main()