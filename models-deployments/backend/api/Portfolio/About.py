from flask import Blueprint, jsonify,send_file, current_app
from db.config import get_connection
import os

About_blueprint = Blueprint('About', __name__)

@About_blueprint.route('/Skilldata', methods=['GET'])
def get_skill_data():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch categories
        cursor.execute("SELECT * FROM skills_categories")
        categories = cursor.fetchall()

        # Fetch skills
        cursor.execute("SELECT * FROM individual_skills")
        skills = cursor.fetchall()

        # Merge data
        skills_data = []
        for cat in categories:
            cat_skills = [
                {
                    "id": skill["skill_id"],
                    "skill": skill["skill_name"],
                    "category": skill["category"],
                    "color": skill["color"],
                    "proficiency": skill["proficiency"],
                    "stage": skill["stage"],
                    "description": skill["description"],
                    "image": skill["image"],
                }
                for skill in skills if skill["skill_category_id"] == cat["id"]
            ]

            skills_data.append({
                "_id": str(cat["id"]),
                "description": cat["description"],
                "experienceLevel": cat["experience_level"],
                "title": cat["title"],
                "skills": cat_skills,
            })

        return jsonify(skills_data), 200

    except Exception as e:
        print("❌ Error fetching skills:", e)
        return jsonify({"error": "Failed to fetch skills"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@About_blueprint.route('/Educationdata', methods=['GET'])
def get_education_data():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # ✅ Fetch education data
        cursor.execute("SELECT * FROM education")
        result = cursor.fetchall()

        return jsonify(result), 200

    except Exception as e:
        print("❌ Error fetching education data:", e)
        return jsonify({"error": "Failed to fetch education data"}), 500

    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@About_blueprint.route('/Certificatesdata', methods=['GET'])
def get_certificates():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # ✅ Fetch certificates data
        cursor.execute("SELECT * FROM certifications")
        result = cursor.fetchall()

        return jsonify(result), 200

    except Exception as e:
        print("❌ Error fetching certificates:", e)
        return jsonify({"error": "Failed to fetch certificates"}), 500

    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@About_blueprint.route("/resume", methods=["GET"])
def download_resume():
    try:
        # Construct the full file path
        file_path = os.path.join(current_app.root_path, "files", "resume.pdf")

        # Check if file exists
        if not os.path.exists(file_path):
            return {"error": "File not found"}, 404

        # send_file handles content type and attachment headers
        return send_file(
            file_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="Achinta_Resume.pdf"
        )

    except Exception as err:
        print("File download error:", err)
        return {"error": "Download failed", "message": str(err)}, 500
