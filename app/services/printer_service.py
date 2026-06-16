"""Printer Service"""
import socket
from datetime import datetime
from extensions import db
from app.models import PrinterConfig, PrintLog, OrderItem

def print_kot(order_id: int, order_item_ids: list, branch_id: int) -> PrintLog:
    """Prints a Kitchen Order Ticket."""
    printer = PrinterConfig.query.filter_by(branch_id=branch_id, printer_role='kitchen', is_enabled=1).first()
    if not printer:
        return None
        
    text = f"KOT - Order {order_id}\n"
    for item_id in order_item_ids:
        item = db.session.get(OrderItem, item_id)
        if item:
            text += f"{item.quantity}x Item {item.item_id} (Seat {item.seat_number})\n"
    text += "\n"
    
    log = PrintLog(branch_id=branch_id, printer_config_id=printer.printer_config_id, reference_type='kot', reference_id=order_id, status='queued')
    db.session.add(log)
    db.session.flush()
    
    try:
        success = _send_to_printer(printer.ip_address, printer.port, text.encode('utf-8'))
        log.status = 'sent' if success else 'failed'
        if success:
            log.sent_at = datetime.utcnow()
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)[:500]
        
    db.session.commit()
    return log

def print_receipt(payment_id: int, branch_id: int) -> PrintLog:
    """Prints a receipt for a payment."""
    printer = PrinterConfig.query.filter_by(branch_id=branch_id, printer_role='receipt', is_enabled=1).first()
    if not printer:
        return None
        
    text = f"RECEIPT - Payment {payment_id}\nThank you!\n"
    
    log = PrintLog(branch_id=branch_id, printer_config_id=printer.printer_config_id, reference_type='receipt', reference_id=payment_id, status='queued')
    db.session.add(log)
    db.session.flush()
    
    try:
        success = _send_to_printer(printer.ip_address, printer.port, text.encode('utf-8'))
        log.status = 'sent' if success else 'failed'
        if success:
            log.sent_at = datetime.utcnow()
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)[:500]
        
    db.session.commit()
    return log

def _send_to_printer(ip: str, port: int, data: bytes) -> bool:
    """Sends raw bytes to an ESC/POS printer via TCP socket."""
    if not ip or not port:
        return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)
            s.connect((ip, port))
            s.sendall(data)
        return True
    except socket.error:
        return False

def test_connection(ip: str, port: int) -> tuple[bool, str]:
    """Tests if a printer is reachable on the network."""
    if not ip or not port:
        return False, "Printer address or port is invalid"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)
            s.connect((ip, port))
            # Just test the connection, no need to send data
        return True, "Connected successfully"
    except socket.timeout:
        return False, "Printer not reachable (connection timed out)"
    except ConnectionRefusedError:
        return False, "Printer is online but port is closed"
    except socket.error:
        return False, "Printer is offline or on a different network"

def reprint(print_log_id: int) -> PrintLog:
    """Reprints a previous print job."""
    log = db.session.get(PrintLog, print_log_id)
    if not log:
        raise ValueError("Print log not found")
        
    printer = db.session.get(PrinterConfig, log.printer_config_id)
    if not printer:
        raise ValueError("Printer not found")
        
    try:
        success = _send_to_printer(printer.ip_address, printer.port, b"REPRINT\n")
        log.status = 'sent' if success else 'failed'
        if success:
            log.sent_at = datetime.utcnow()
            log.error_message = None
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)[:500]
        
    db.session.commit()
    return log
