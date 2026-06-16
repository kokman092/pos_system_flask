import datetime
from extensions import db
from sqlalchemy import CheckConstraint

# DOMAIN 9 — KDS

class KdsStation(db.Model):
    __tablename__ = 'kds_stations'
    station_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_kds_branch'))
    name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.SmallInteger, default=1)

    def __repr__(self):
        return f'<KdsStation {self.name}>'

    logs = db.relationship('KdsLog', backref='station')

class KdsLog(db.Model):
    __tablename__ = 'kds_logs'
    kds_log_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.order_item_id', name='fk_kdslog_oi'))
    station_id = db.Column(db.Integer, db.ForeignKey('kds_stations.station_id', name='fk_kdslog_station'), nullable=True)
    displayed_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    mitigation_time_minutes = db.Column(db.Integer)

    def __repr__(self):
        return f'<KdsLog {self.kds_log_id}>'

    order_item = db.relationship('OrderItem', foreign_keys=[order_item_id])

