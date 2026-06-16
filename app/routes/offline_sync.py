from flask import Blueprint, request
from flask_login import login_required, current_user
from app.models import OfflineSyncLog
from extensions import db
from app.utils.response import success_response, error_response
import json
import uuid as uuid_module

offline_sync_bp = Blueprint('offline_sync', __name__, url_prefix='/sync')

@offline_sync_bp.route('/orders', methods=['POST'])
@login_required
def sync_orders():
    """Syncs offline orders, checking for duplicate client_uuid."""
    data = request.json
    uuid = data.get('client_uuid')
    
    if not uuid:
        return error_response("client_uuid is required", 422)

    # Validate UUID4 format
    try:
        uuid_module.UUID(uuid, version=4)
    except (ValueError, AttributeError):
        return error_response("client_uuid must be a valid UUID4", 422)
    
    existing = OfflineSyncLog.query.filter_by(client_uuid=uuid).first()
    if existing:
        return success_response({"status": "duplicate"})
        
    try:
        new_log = OfflineSyncLog(
            branch_id=current_user.branch_id,
            client_uuid=uuid,
            payload_json=json.dumps(data),
            sync_status='synced'
        )
        db.session.add(new_log)
        db.session.commit()
        return success_response({"status": "synced", "created_ids": []})
    except Exception as e:
        db.session.rollback()
        return error_response(str(e))

