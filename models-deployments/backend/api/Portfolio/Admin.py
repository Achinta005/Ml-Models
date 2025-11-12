from flask import Blueprint, request, jsonify
import os
import requests
from db.config import get_connection
from datetime import datetime
import json
import re
import jwt

Admin_blueprint = Blueprint('Admin_blueprint', __name__)

@Admin_blueprint.route('/ai-enhance', methods=['POST'])
def summarize_text():
    try:
        data = request.get_json()
        text = data.get('text', '').strip() if data else ''

        if not text:
            return jsonify({"error": "Text is required"}), 400

        HF_API_TOKEN = os.getenv("HF_API_TOKEN")

        if not HF_API_TOKEN:
            return jsonify({"error": "API token not configured"}), 500

        url = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

        payload = {
            "inputs": text[:10000],
            "parameters": {
                "max_length": 1024,
                "min_length": 100,
                "do_sample": False
            }
        }

        headers = {
            "Authorization": f"Bearer {HF_API_TOKEN}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=payload)

        if not response.ok:
            error_text = response.text
            print("Hugging Face API error:", error_text)

            if response.status_code == 503:
                return jsonify({
                    "error": "Model is loading, please try again in a moment",
                    "loading": True
                }), 503

            return jsonify({
                "error": "Failed to enhance text",
                "details": error_text
            }), response.status_code

        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            if "summary_text" in data[0]:
                return jsonify({"summary": data[0]["summary_text"]})
            elif "generated_text" in data[0]:
                return jsonify({"summary": data[0]["generated_text"]})
        elif isinstance(data, dict) and "summary_text" in data:
            return jsonify({"summary": data["summary_text"]})

        print("Unexpected response format:", data)
        return jsonify({"summary": text}) 

    except Exception as e:
        print("API route error:", e)
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

def validate_blog_post_data(data):
    title = data.get('title')
    excerpt = data.get('excerpt')
    content = data.get('content')

    if not title or not excerpt or not content:
        raise ValueError("Title, excerpt, and content are required")

@Admin_blueprint.route('/upload_blog', methods=['POST'])
def create_blog_post():
    connection = None
    try:
        form_data = request.get_json()
        validate_blog_post_data(form_data)

        title = form_data.get('title')
        excerpt = form_data.get('excerpt')
        content = form_data.get('content')
        tags = form_data.get('tags', [])
        date = form_data.get('date', datetime.now().isoformat())
        read_time = form_data.get('readTime', '5 min')
        slug = form_data.get('slug')

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT post_id FROM blog_data ORDER BY post_id DESC LIMIT 1")
        last_post = cursor.fetchall()
        next_post_id = last_post[0]['post_id'] + 1 if last_post else 1

        if not slug:
            slug = re.sub(r'[^a-z0-9\s-]', '', title.lower())
            slug = re.sub(r'\s+', '-', slug)
            slug = re.sub(r'-+', '-', slug)
            slug = re.sub(r'^-|-$', '', slug)

        cursor.execute("SELECT post_id FROM blog_data WHERE slug = %s", (slug,))
        existing_slug = cursor.fetchall()

        if existing_slug:
            slug = f"{slug}-{next_post_id}"

        tags_json = json.dumps(tags)

        cursor.execute("""
            INSERT INTO blog_data 
            (post_id, title, content, excerpt, slug, tags, date, readTime, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            next_post_id,
            title,
            content,
            excerpt,
            slug,
            tags_json,
            date,
            read_time
        ))

        connection.commit()

        return jsonify({
            "id": next_post_id,
            "title": title,
            "slug": slug,
            "excerpt": excerpt,
            "content": content,
            "date": date,
            "readTime": read_time,
            "tags": tags
        }), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    except Exception as e:
        print("Error creating blog post:", e)
        return jsonify({
            "error": "Error creating blog post",
            "message": str(e)
        }), 500

    finally:
        if connection:
            connection.close()

@Admin_blueprint.route("/get-ip", methods=["POST"])
def save_ip():
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    ip_address = request.headers.get("X-Forwarded-For")
    if ip_address:
        ip_address = ip_address.split(",")[0].strip()
    else:
        ip_address = request.headers.get("X-Real-IP")

    if not ip_address or ip_address in ["::1", "127.0.0.1"]:
        try:
            response = requests.get("https://api.ipify.org?format=json")
            ip_address = response.json().get("ip")
        except Exception:
            return jsonify({"error": "Unable to detect IP", "source": "localhost"}), 500

    conn = get_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT user_id FROM ipaddress WHERE ipaddress = %s LIMIT 1", (ip_address,))
        row = cursor.fetchone()

        if row:
            cursor.close()
            conn.close()
            return jsonify({
                "ip": ip_address,
                "user_id": row["user_id"],
                "status": "existing",
                "source": "database"
            }), 200

        cursor.execute(
            "INSERT INTO ipaddress (user_id, ipaddress) VALUES (%s, %s)",
            (user_id, ip_address)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "ip": ip_address,
            "user_id": user_id,
            "status": "inserted",
            "source": "headers"
        }), 201

    except Exception as e:
        print("Database operation failed:", e)
        return jsonify({"error": "Database operation failed"}), 500

@Admin_blueprint.route("/get-ip", methods=["GET"])
def get_only_ip():
    ip_address = request.headers.get("X-Forwarded-For")
    if ip_address:
        ip_address = ip_address.split(",")[0].strip()
    else:
        ip_address = request.headers.get("X-Real-IP")

    if not ip_address:
        ip_address = request.remote_addr

    if ip_address in ["::1", "127.0.0.1"]:
        try:
            response = requests.get("https://api.ipify.org?format=json", timeout=3)
            ip_address = response.json().get("ip")
            source = "external (ipify.org)"
        except Exception:
            return jsonify({"error": "Unable to detect public IP", "source": "localhost"}), 500
    else:
        source = "request headers or remote_addr"

    return jsonify({"IP": ip_address, "source": source})


@Admin_blueprint.route("/view-ip", methods=["GET"])
def get_ip_addresses():
    connection = None
    try:
        connection = get_connection()
        if not connection:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT 
                u.id, 
                u.username, 
                i.ipaddress, 
                i.timestamp 
            FROM usernames u 
            LEFT JOIN ipaddress i 
            ON u.id = i.user_id 
            ORDER BY i.timestamp DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        return jsonify(rows), 200

    except Exception as err:
        if connection:
            connection.close()
        return jsonify({
            "error": "Failed to fetch IP addresses",
            "message": str(err)
        }), 500


JWT_SECRET = os.getenv("JWT_SECRET", "your_jwt_secret")
def get_user_from_token(req):
    try:
        auth_header = req.headers.get("Authorization")
        if not auth_header:
            return None

        token = auth_header.replace("Bearer ", "")
        user = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return user
    except Exception:
        return None


@Admin_blueprint.route("/fetch_documents", methods=["GET"])
def get_documents():
    user = get_user_from_token(request)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM documents WHERE owner = %s ORDER BY updated_at DESC",
            (user["username"],)
        )
        rows = cursor.fetchall()

        return jsonify(rows), 200

    except Exception as err:
        print("Error fetching documents:", err)
        return jsonify({"error": "Failed to fetch documents"}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@Admin_blueprint.route("/create_documents", methods=["POST"])
def create_document():
    user = get_user_from_token(request)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json()
        title = data.get("title")
        content = data.get("content")

        if not title or not content:
            return jsonify({"error": "Title and content required"}), 400

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO documents(owner, title, content, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            """,
            (user["username"], title, content),
        )
        conn.commit()

        return (
            jsonify({"message": "Document created", "id": cursor.lastrowid}),
            201,
        )

    except Exception as err:
        print("Error creating document:", err)
        return jsonify({"error": "Server error", "message": str(err)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()
