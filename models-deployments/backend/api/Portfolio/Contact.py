from flask import Blueprint, request, jsonify
from db.config import get_connection
from datetime import datetime

contact_bp = Blueprint("contact", __name__)

@contact_bp.route("/upload_response", methods=["POST"])
def submit_contact_form():
    try:
        body = request.get_json()
        name = body.get("name")
        email = body.get("email")
        subject = body.get("subject")
        message = body.get("message")

        if not all([name, email, subject, message]):
            return jsonify({"message": "All fields are required"}), 400

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO contact_info (name, email, subject, message, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (name, email, subject, message)
        )
        conn.commit()

        return jsonify({"message": "Form submitted successfully!"}), 200

    except Exception as err:
        print("Error submitting contact form:", err)
        return jsonify({"message": "Server error", "error": str(err)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@contact_bp.route("/contact_responses", methods=["GET"])
def get_contact_info():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM contact_info")
        rows = cursor.fetchall()

        return jsonify(rows), 200

    except Exception as err:
        print("Error fetching contact info:", err)
        return jsonify({
            "error": "Failed to fetch contact info",
            "message": str(err)
        }), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
