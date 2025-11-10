from flask import Blueprint, jsonify,request
from db.config import get_connection
import cloudinary
import cloudinary.uploader
import json
from datetime import datetime
import os

projects_blueprint = Blueprint('projects_data', __name__)

@projects_blueprint.route('/projects_data', methods=['GET'])
def get_projects_data():
    """Fetch all projects from the project_model table"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM project_model ORDER BY order_position DESC")
        result = cursor.fetchall()

        return jsonify(result), 200

    except Exception as e:
        print("Error fetching projects:", e)
        return jsonify({"error": "Failed to fetch projects"}), 500

    finally:
        if conn:
            conn.close()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

@projects_blueprint.route("/project_uplaod", methods=["POST"])
def upload_project():
    try:
        # Extract form fields
        file = request.files.get("image")
        category = request.form.get("category")
        title = request.form.get("title")
        technologies = request.form.get("technologies")
        live_url = request.form.get("liveUrl")
        github_url = request.form.get("githubUrl")
        description = request.form.get("description")
        order = request.form.get("order")

        if not file:
            return jsonify({"error": "Image is required"}), 400

        # Upload image to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file,
            folder="Uploaded_Images",
            resource_type="image"
        )
        image_url = upload_result.get("secure_url")

        # Convert technologies to JSON
        json_technologies = (
            json.dumps(
                [tech.strip() for tech in technologies.split(",") if tech.strip()]
            )
            if technologies
            else "[]"
        )

        # Insert into MySQL
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO project_model 
            (title, description, category, technologies, github_url, live_url, image, order_position, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        cursor.execute(
            query,
            (title, description, category, json_technologies, github_url, live_url, image_url, order)
        )
        conn.commit()

        return jsonify({
            "message": "Uploaded successfully",
            "project_id": cursor.lastrowid
        }), 200

    except Exception as err:
        print("Error:", err)
        return jsonify({"error": str(err)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
