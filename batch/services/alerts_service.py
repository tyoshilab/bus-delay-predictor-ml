from sqlalchemy.orm import Session
from batch.models.realtime.alerts import GTFSRTAlert
from batch.models.realtime.alert_active_periods import GTFSRTAlertActivePeriod
from batch.models.realtime.alert_informed_entities import GTFSRTAlertInformedEntity
from batch.models.realtime.alert_text import GTFSRTAlertText


class AlertsService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create_alert(self, entity_id: int, alert) -> GTFSRTAlert:
        alert_record = GTFSRTAlert(
            feed_entity_id=entity_id,
            cause=alert.cause if alert.HasField('cause') else 'UNKNOWN_CAUSE',
            effect=alert.effect if alert.HasField('effect') else 'UNKNOWN_EFFECT',
            severity_level=alert.severity_level if alert.HasField('severity_level') else 'UNKNOWN_SEVERITY',
        )
        self.db.add(alert_record)
        self.db.commit()
        self.db.refresh(alert_record)
        return alert_record

    def create_alert_active_period(self, alert_id: int, active_period) -> GTFSRTAlertActivePeriod:
        period_time = active_period.start if active_period.HasField('start') else None
        period_time = active_period.end if active_period.HasField('end') else period_time
        active_period_record = GTFSRTAlertActivePeriod(
            alert_id=alert_id,
            period_time=period_time
        )
        self.db.add(active_period_record)
        self.db.commit()
        self.db.refresh(active_period_record)
        return active_period_record

    def create_alert_informed_entity(self, alert_id: int, informed_entity) -> GTFSRTAlertInformedEntity:
        informed_entity_record = GTFSRTAlertInformedEntity(
            alert_id=alert_id,
            agency_id=informed_entity.agency_id if informed_entity.HasField('agency_id') else None,
            route_id=informed_entity.route_id if informed_entity.HasField('route_id') else None,
            route_type=informed_entity.route_type if informed_entity.HasField('route_type') else None,
            stop_id=informed_entity.stop_id if informed_entity.HasField('stop_id') else None
        )
        self.db.add(informed_entity_record)
        self.db.commit()
        self.db.refresh(informed_entity_record)
        return informed_entity_record

    def create_alert_text(self, alert_id: int, text, text_type) -> GTFSRTAlertText:
        text_record = GTFSRTAlertText(
            alert_id=alert_id,
            text_type=text_type,
            text=text.text if text.HasField('text') else None,
            language=text.language if text.HasField('language') else 'en'
        )
        self.db.add(text_record)
        self.db.commit()
        self.db.refresh(text_record)
        return text_record
