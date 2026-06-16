import datetime
from extensions import db
from sqlalchemy import CheckConstraint

# DOMAIN 12 — Offline Sync

class OfflineSyncLog(db.Model):
    __tablename__ = 'offline_sync_logs'
    sync_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_offsync_branch'))
    client_uuid = db.Column(db.String(36), unique=True, nullable=False)
    payload_json = db.Column(db.Text)
    sync_status = db.Column(db.String(15), CheckConstraint("sync_status IN ('pending','synced','failed','duplicate')", name='chk_offsync_status'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    synced_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<OfflineSyncLog {self.sync_id}>'
