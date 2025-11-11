from flask import Blueprint, jsonify, request, redirect,make_response, current_app
from db.config import get_connection
from datetime import datetime,timedelta
import bcrypt
import jwt
import os
import requests

Authentication_blueprint = Blueprint('Authentication_blueprint', __name__)

@Authentication_blueprint.route('/register',methods=['POST'])
def register_user():
    connection=None
    try:
        data=request.get_json()
        username=data.get('username')
        password=data.get('password')
        role=data.get('role','viewer')
        email=data.get('email')
        
        if not username or not password:
            return jsonify({"error":"Username and Password required"}),400
        
        connection=get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM usernames WHERE username=%s LIMIT 1",(username,))
        existing=cursor.fetchall()
        
        if existing:
            return jsonify({"error": "User with this Username already exists."}), 400
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        cursor.execute("""
            INSERT INTO usernames 
            (username, password, role, version_key, created_at, updated_at,Email)
            VALUES (%s, %s, %s, %s, NOW(), NOW(),%s)
        """, (username, hashed_password.decode('utf-8'), role, 0,email))
        connection.commit()
        
        user_id = cursor.lastrowid
        
        user_data = {
            "id": user_id,
            "username": username,
            "role": role,
            "version_key": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        return jsonify({
            "message": "User registered successfully",
            "user": user_data
        }), 201
    except Exception as e:
        print("Error registering user:", e)
        return jsonify({"error": "Error registering user", "message": str(e)}), 500
    
    finally:
        if connection:
            connection.close()

@Authentication_blueprint.route('/login', methods=['POST'])
def login_user():
    connection = None
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        # Validate input
        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT * FROM usernames WHERE username = %s LIMIT 1", (username,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        # Verify password
        is_match = bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8'))
        if not is_match:
            return jsonify({"error": "Invalid credentials"}), 401

        # Generate JWT token
        secret_key = os.getenv("JWT_SECRET", "your_jwt_secret")
        payload = {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "exp": datetime.utcnow() + timedelta(hours=2)
        }
        token = jwt.encode(payload, secret_key, algorithm="HS256")

        return jsonify({"token": token}), 200

    except Exception as e:
        print("Login error:", e)
        return jsonify({"error": "Login error", "message": str(e)}), 500

    finally:
        if connection:
            connection.close()


@Authentication_blueprint.route("/google-oAuth", methods=["GET"])
def google_auth_redirect():
    try:
        redirect_uri = os.environ.get("REDIRECT_URL")
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        scope = "email profile"
        response_type = "code"
        access_type = "offline"

        oauth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type={response_type}&"
            f"scope={scope}&"
            f"access_type={access_type}"
        )

        return redirect(oauth_url)

    except Exception as e:
        return {"error": "Failed to redirect", "message": str(e)}, 500


@Authentication_blueprint.route("/google_auth_callback", methods=["GET"])
def google_oauth_callback():
    code = request.args.get("code")
    if not code:
        return {"error": "Missing authorization code"}, 400

    try:
        # 1️⃣ Exchange code for access token
        token_resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": os.environ.get("REDIRECT_URL"),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")

        # 2️⃣ Fetch user info
        user_info_resp = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info_resp.raise_for_status()
        user_data = user_info_resp.json()
        print("userdatagoogle:",user_data)

        username = user_data.get("name")
        password = user_data.get("id")  # Using Google ID as password
        email=user_data.get("email")
        role = "editor"

        # 3️⃣ Check if user exists in MySQL
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usernames WHERE username = %s LIMIT 1", (username,))
        user = cursor.fetchone()

        if user:
            # Compare passwords
            if not bcrypt.checkpw(password.encode(), user["password"].encode()):
                return {"error": "Username already exists with a different password"}, 400
        else:
            # 4️⃣ Create new user
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cursor.execute(
                "INSERT INTO usernames (username, password, role, version_key, created_at, updated_at,Email) "
                "VALUES (%s, %s, %s, 0, NOW(), NOW(),%s)",
                (username, hashed_pw, role,email)
            )
            conn.commit()
            user = {"id": cursor.lastrowid, "username": username, "role": role}

        cursor.close()
        conn.close()

        # 5️⃣ Generate JWT token
        token = jwt.encode(
            {"id": user["id"], "username": user["username"], "role": user["role"]},
            os.environ.get("JWT_SECRET", "your_jwt_secret"),
            algorithm="HS256"
        )

        # 6️⃣ Redirect to frontend with token
        redirect_url = f"{os.environ.get('NEXT_PUBLIC_FRONTEND_URL')}/login?token={token}"
        return redirect(redirect_url)

    except requests.HTTPError as e:
        return {"error": "OAuth failed", "details": str(e)}, 500
    except Exception as e:
        return {"error": "Server error", "details": str(e)}, 500



SECRET_KEY = os.getenv("ADMIN_GRANT_KEY", "default_admin_grant_key")

def get_client_ip():
    # Check headers first
    ip_address = request.headers.get("X-Forwarded-For")
    if ip_address:
        ip_address = ip_address.split(",")[0].strip()
    else:
        ip_address = request.headers.get("X-Real-IP")

    # Fallback for localhost/dev
    if not ip_address or ip_address in ["::1", "127.0.0.1"]:
        try:
            response = requests.get("https://api.ipify.org?format=json", timeout=2)
            ip_address = response.json().get("ip")
        except Exception:
            ip_address = None

    return ip_address

@Authentication_blueprint.route("/check-access", methods=["POST"])
def check_access():
    ip_address = get_client_ip()
    if not ip_address:
        return jsonify({"allowed": False, "error": "Unable to detect IP"}), 400

    conn = None
    cursor = None
    row = None  # initialize row here

    try:
        # Get DB connection
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if IP exists in DB
        cursor.execute("SELECT 1 FROM admin_ipaddress WHERE ipaddress = %s LIMIT 1", (ip_address,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"allowed": False}), 403

        # IP exists -> generate JWT token valid for 10 minutes
        token = jwt.encode(
            {
                "purpose": "admin_access",
                "ip": ip_address,
                "exp": datetime.utcnow() + timedelta(minutes=10)
            },
            SECRET_KEY,
            algorithm="HS256"
        )

        return jsonify({"allowed": True, "token": token, "expires_in": 600})

    except Exception as e:
        return jsonify({"allowed": False, "error": str(e)}), 500

    finally:
        # Safely close cursor and connection
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print("Error closing cursor:", e)
        if conn:
            try:
                conn.close()
            except Exception as e:
                print("Error closing connection:", e)


    