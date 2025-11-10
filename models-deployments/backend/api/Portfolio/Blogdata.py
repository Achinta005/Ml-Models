from flask import Blueprint, jsonify, abort
from db.config import get_connection

blog_blueprint = Blueprint('blog_blueprint', __name__)

# --- GET all blog posts ---
@blog_blueprint.route('/blog_data', methods=['GET'])
def get_all_blogs():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM blog_data ORDER BY date DESC")
        rows = cursor.fetchall()

        posts = [
            {
                "id": row["post_id"],
                "title": row["title"],
                "slug": row["slug"],
                "excerpt": row["excerpt"],
                "content": row["content"],
                "date": row["date"],
                "readTime": row["readTime"],
                "tags": (
                    row["tags"].split(",")
                    if row["tags"] and isinstance(row["tags"], str)
                    else []
                ),
            }
            for row in rows
        ]

        return jsonify(posts), 200

    except Exception as e:
        print("Error fetching blog posts:", e)
        return jsonify({"error": "Error fetching blog posts", "message": str(e)}), 500

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# --- GET a single blog post by slug ---
@blog_blueprint.route('/blog_data/<slug>', methods=['GET'])
def get_blog_by_slug(slug):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM blog_data WHERE slug = %s LIMIT 1", (slug,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Post not found"}), 404

        post = {
            "id": row["post_id"],
            "title": row["title"],
            "slug": row["slug"],
            "excerpt": row["excerpt"],
            "content": row["content"],
            "date": row["date"],
            "readTime": row["readTime"],
            "tags": (
                row["tags"].split(",")
                if row["tags"] and isinstance(row["tags"], str)
                else []
            ),
        }

        return jsonify(post), 200

    except Exception as e:
        print("Error fetching blog post:", e)
        return jsonify({"error": "Error fetching blog post", "message": str(e)}), 500

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
