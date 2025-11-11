from flask import Blueprint, request, jsonify
from db.config import get_connection
import re

# Create blueprint
ip_routes = Blueprint('ip_routes', __name__)

# IP address validation regex
IP_PATTERN = re.compile(
    r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
)

def validate_ip(ip):
    """Validate IP address format"""
    return bool(IP_PATTERN.match(ip))


@ip_routes.route('/ips', methods=['GET'])
def get_all_ips():
    """Get all IP addresses from database"""
    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, ipaddress, created_at 
            FROM admin_ipaddress 
            ORDER BY created_at DESC
        """)
        
        ips = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'ips': ips,
            'count': len(ips)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@ip_routes.route('/ips', methods=['POST'])
def add_ip():
    """Add a new IP address to database"""
    conn = None
    cursor = None
    
    try:
        data = request.get_json()
        
        if not data or 'ipaddress' not in data:
            return jsonify({
                'success': False,
                'error': 'IP address is required'
            }), 400
        
        ipaddress = data['ipaddress'].strip()
        
        if not validate_ip(ipaddress):
            return jsonify({
                'success': False,
                'error': 'Invalid IP address format'
            }), 400
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT id FROM admin_ipaddress WHERE ipaddress = %s",
            (ipaddress,)
        )
        
        if cursor.fetchone():
            return jsonify({
                'success': False,
                'error': 'IP address already exists'
            }), 409
        
        cursor.execute(
            "INSERT INTO admin_ipaddress (ipaddress) VALUES (%s)",
            (ipaddress,)
        )
        
        conn.commit()
        
        cursor.execute(
            "SELECT id, ipaddress, created_at FROM admin_ipaddress WHERE id = %s",
            (cursor.lastrowid,)
        )
        
        new_ip = cursor.fetchone()
        
        return jsonify({
            'success': True,
            'message': 'IP address added successfully',
            'ip': new_ip
        }), 201
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@ip_routes.route('/ips/<int:ip_id>', methods=['DELETE'])
def delete_ip(ip_id):
    """Delete an IP address from database"""
    conn = None
    cursor = None
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT id, ipaddress FROM admin_ipaddress WHERE id = %s",
            (ip_id,)
        )
        
        ip_record = cursor.fetchone()
        
        if not ip_record:
            return jsonify({
                'success': False,
                'error': 'IP address not found'
            }), 404
        
        cursor.execute(
            "DELETE FROM admin_ipaddress WHERE id = %s",
            (ip_id,)
        )
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'IP address deleted successfully',
            'deleted_ip': ip_record
        }), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
