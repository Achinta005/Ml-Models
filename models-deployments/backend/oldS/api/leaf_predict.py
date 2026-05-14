from flask import Blueprint, request, jsonify
import os
from werkzeug.utils import secure_filename
import uuid

predict_leaf_name = Blueprint('predict_leaf_name', __name__)

# Folder where uploaded files will be stored
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads", "leaf_predictions")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Allowed image types
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# --- PREDICTION ROUTE ---
@predict_leaf_name.route('/leaf_prediction', methods=['POST'])
def leaf_prediction():
    print("📌 Leaf detection route hit...")

    try:
        # Check if file exists
        if "image" not in request.files:
            print("❌ No file part in request")
            return jsonify({"success": False, "message": "No image in request"}), 400

        file = request.files["image"]

        # Validate filename
        if not file or not file.filename:
            print("❌ Empty filename received")
            return jsonify({"success": False, "message": "Empty filename"}), 400

        # Validate extension
        if not allowed_file(file.filename):
            print(f"❌ Invalid file type rejected: {file.filename}")
            return jsonify({"success": False, "message": "File type not allowed"}), 400
        
        # Secure filename
        filename = secure_filename(file.filename)

        # Generate strongly unique saved name
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        print(f"📥 Saving file to: {file_path}")

        try:
            file.save(file_path)
        except Exception as e:
            print(f"❌ Error saving file: {e}")
            return jsonify({
                "success": False,
                "message": "Failed to save file",
                "error": str(e)
            }), 500
        
        print("✅ Leaf image saved successfully")

        return jsonify({
            "success": True,
            "message": "Leaf image stored successfully",
            "stored_at": file_path,
            "file_name": unique_filename
        }), 200

    except Exception as general_error:
        print(f"🔥 Unexpected Error in /leaf_prediction: {general_error}")
        
        # Attempt cleanup if file exists and caused issue
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print("🧹 Cleanup: Removed partially saved file")
            except:
                print("⚠️ Cleanup failed for problematic file")

        return jsonify({
            "success": False,
            "message": "Unexpected server error occurred",
            "error": str(general_error)
        }), 500
        
        
