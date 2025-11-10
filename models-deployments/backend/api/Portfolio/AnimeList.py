from flask import Blueprint, jsonify, request, make_response, redirect, current_app
from db.config2 import get_connection
import requests
import json
from datetime import date, datetime, timedelta
import os
import secrets
from urllib.parse import urlencode

AnimeList_bp = Blueprint('AnimeList_bp', __name__)

# ============================================================================
# ANILIST GRAPHQL QUERIES
# ============================================================================

ANILIST_QUERY = """
query ($username: String) {
  MediaListCollection(userName: $username, type: ANIME) {
    lists {
      name
      status
      entries {
        id
        mediaId
        status
        score
        progress
        repeat
        startedAt { year month day }
        completedAt { year month day }
        updatedAt
        createdAt
        media {
          id
          title { romaji english native }
          coverImage { large medium }
          bannerImage
          episodes
          format
          status
          season
          seasonYear
          genres
          averageScore
          description
        }
      }
    }
  }
}
"""

SEARCH_ANIME_QUERY = """
query ($search: String) {
  Page(page: 1, perPage: 20) {
    media(search: $search, type: ANIME) {
      id
      title { romaji english native }
      coverImage { large medium }
      bannerImage
      episodes
      format
      genres
      averageScore
      description
    }
  }
}
"""

# ============================================================================
# DATABASE SETUP
# ============================================================================

def create_tables():
    """Create necessary database tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Anime list table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anime_list (
            id INT PRIMARY KEY,
            username VARCHAR(255),
            media_id INT,
            list_name VARCHAR(100),
            status VARCHAR(50),
            score FLOAT,
            progress INT,
            repeat_count INT,
            started_at DATE,
            completed_at DATE,
            updated_at BIGINT,
            created_at BIGINT,
            synced_at DATETIME,
            INDEX idx_username (username),
            INDEX idx_media_id (media_id),
            INDEX idx_status (status)
        )
    """)
    
    # Anime details table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anime_details (
            id INT PRIMARY KEY,
            title_romaji VARCHAR(500),
            title_english VARCHAR(500),
            title_native VARCHAR(500),
            cover_image_large VARCHAR(500),
            cover_image_medium VARCHAR(500),
            banner_image VARCHAR(500),
            episodes INT,
            format VARCHAR(50),
            status VARCHAR(50),
            season VARCHAR(50),
            season_year INT,
            genres JSON,
            average_score INT,
            description TEXT
        )
    """)
    
    # AniList tokens table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anilist_tokens (
            username VARCHAR(255) PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def query_anilist(query, variables=None, token=None):
    """Send a GraphQL request to AniList API"""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.post(
        "https://graphql.anilist.co",
        json={"query": query, "variables": variables or {}},
        headers=headers
    )

    data = response.json()
    if "errors" in data:
        raise Exception(data["errors"][0].get("message", "AniList API error"))

    return data["data"]


def fetch_from_anilist(username):
    """Fetch anime list from AniList"""
    data = query_anilist(ANILIST_QUERY, {"username": username})
    return data["MediaListCollection"]["lists"]

def has_data_changed(username, new_lists):
    """Check if anime list has changed"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    new_entries = []
    for lst in new_lists:
        for entry in lst["entries"]:
            new_entries.append({
                "id": entry["id"],
                "status": entry["status"],
                "score": entry["score"],
                "progress": entry["progress"],
                "updatedAt": entry["updatedAt"]
            })

    cursor.execute(
        "SELECT id, status, score, progress, updated_at FROM anime_list WHERE username = %s",
        (username,)
    )
    existing_rows = cursor.fetchall()
    # print("Fetched animelist:-",existing_rows)
    conn.close()

    if len(new_entries) != len(existing_rows):
        return True

    existing_map = {row["id"]: row for row in existing_rows}
    for entry in new_entries:
        ex = existing_map.get(entry["id"])
        if not ex or (
            ex["status"] != entry["status"] or
            ex["score"] != entry["score"] or
            ex["progress"] != entry["progress"] or
            ex["updated_at"] != entry["updatedAt"]
        ):
            return True

    return False

def store_in_database(username, lists):
    """Store anime list and details in the database"""
    conn = get_connection()
    cursor = conn.cursor()

    # Remove old entries for this user
    cursor.execute("DELETE FROM anime_list WHERE username = %s", (username,))

    for lst in lists:
        list_name = lst.get("name")
        for entry in lst.get("entries", []):
            media = entry.get("media", {})

            # Safely format dates
            started = entry.get("startedAt", {})
            completed = entry.get("completedAt", {})

            started_at = (
                f"{started.get('year', 0)}-{started.get('month', 1)}-{started.get('day', 1)}"
                if started.get("year") else None
            )
            completed_at = (
                f"{completed.get('year', 0)}-{completed.get('month', 1)}-{completed.get('day', 1)}"
                if completed.get("year") else None
            )

            # Insert into anime_list
            cursor.execute("""
                INSERT INTO anime_list (
                    id, username, media_id, list_name, status, score, progress,
                    repeat_count, started_at, completed_at, updated_at, created_at, synced_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON DUPLICATE KEY UPDATE
                    status=VALUES(status),
                    score=VALUES(score),
                    progress=VALUES(progress),
                    synced_at=NOW()
            """, (
                entry.get("id"),
                username,
                entry.get("mediaId"),
                list_name,
                entry.get("status"),
                entry.get("score"),
                entry.get("progress"),
                entry.get("repeat"),
                started_at,
                completed_at,
                entry.get("updatedAt"),
                entry.get("createdAt")
            ))

            # Insert into anime_details (banner_image removed)
            cursor.execute("""
                INSERT INTO anime_details (
                    id, title_romaji, title_english, title_native,
                    cover_image_large, cover_image_medium,
                    episodes, format, status, season, season_year,
                    genres, average_score, description
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    title_romaji=VALUES(title_romaji),
                    title_english=VALUES(title_english),
                    episodes=VALUES(episodes),
                    average_score=VALUES(average_score)
            """, (
                media.get("id"),
                media.get("title", {}).get("romaji"),
                media.get("title", {}).get("english"),
                media.get("title", {}).get("native"),
                media.get("coverImage", {}).get("large"),
                media.get("coverImage", {}).get("medium"),
                media.get("episodes"),
                media.get("format"),
                media.get("status"),
                media.get("season"),
                media.get("seasonYear"),
                json.dumps(media.get("genres")),
                media.get("averageScore"),
                media.get("description")
            ))

    conn.commit()
    conn.close()
    return len([e for lst in lists for e in lst.get("entries", [])])


def fetch_from_database(username):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            al.*, ad.title_romaji, ad.title_english, ad.title_native,
            ad.cover_image_large, ad.cover_image_medium,
            ad.episodes, ad.format, ad.genres, ad.average_score, ad.description
        FROM anime_list al
        LEFT JOIN anime_details ad ON al.media_id = ad.id
        WHERE al.username = %s
        ORDER BY al.updated_at DESC
    """, (username,))

    rows = cursor.fetchall()
    for r in rows:
        if isinstance(r.get("genres"), str):
            try:
                r["genres"] = json.loads(r["genres"])
            except:
                r["genres"] = []
    conn.close()
    return rows

def get_anilist_token(username):
    """Retrieve valid AniList token from database"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT access_token, expires_at FROM anilist_tokens WHERE username=%s",
        (username,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row or datetime.utcnow() > row["expires_at"]:
        return None
    return row["access_token"]

def store_anilist_token(username, access_token, refresh_token, expires_in):
    """Store AniList token in database"""
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO anilist_tokens (username, access_token, refresh_token, expires_at)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            access_token = VALUES(access_token),
            refresh_token = VALUES(refresh_token),
            expires_at = VALUES(expires_at)
    """, (username, access_token, refresh_token, expires_at))
    conn.commit()
    conn.close()

# ============================================================================
# ROUTES - FETCH & SYNC
# ============================================================================

@AnimeList_bp.route("/anilist/BaseFunction/fetch", methods=["POST"])
def sync_anilist():
    """Fetch and sync anime list from AniList"""
    try:
        data = request.get_json()
        username = data.get("username")

        if not username:
            return jsonify({"error": "Username is required"}), 400

        try:
            lists = fetch_from_anilist(username)
            fetched = True
        except Exception as e:
            fetched = False
            print(f"AniList fetch failed: {str(e)}")
            lists = None
        if not fetched or lists is None:
            print("List not fetched from anilist , giving cached data....")
            cached = fetch_from_database(username)
            if not cached:
                return jsonify({"error": "No cached data found"}), 500
            return jsonify({
                "success": True,
                "username": username,
                "count": len(cached),
                "animeList": cached,
                "cached": True,
                "message": "Returned cached data (AniList fetch failed)"
            }), 200

        if not has_data_changed(username, lists):
            print("Data not changed giving cached data....")
            cached = fetch_from_database(username)
            return jsonify({
                "success": True,
                "username": username,
                "count": len(cached),
                "animeList": cached,
                "cached": True,
                "message": "No changes detected"
            }), 200
        print("Data changed..............")
        count = store_in_database(username, lists)
        anime_list = fetch_from_database(username)

        return jsonify({
            "success": True,
            "username": username,
            "count": len(anime_list),
            "animeList": anime_list,
            "cached": False,
            "message": "Data synced successfully"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ============================================================================
# ROUTES - EXPORT
# ============================================================================

@AnimeList_bp.route("/anilist/BaseFunction/export", methods=["POST"])
def export_anilist():
    """Export anime list as JSON or XML"""
    try:
        data = request.get_json()
        username = data.get("username")
        format_type = data.get("format", "").lower()
        filter_status = data.get("filter")

        if not username:
            return jsonify({"error": "Username is required"}), 400
        if format_type not in ["json", "xml"]:
            return jsonify({"error": "Invalid format"}), 400

        anime_list = fetch_from_database(username)
        if filter_status and filter_status.upper() != "ALL":
            anime_list = [a for a in anime_list if a["status"] == filter_status]

        if not anime_list:
            return jsonify({"error": "No anime found"}), 404

        def make_json_serializable(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, (bytes, bytearray)):
                return obj.decode("utf-8", errors="ignore")
            return str(obj)

        if format_type == "json":
            content = json.dumps(anime_list, indent=2, ensure_ascii=False, default=make_json_serializable)
            content_type = "application/json; charset=utf-8"
        else:
            content = generate_xml(anime_list)
            content_type = "application/xml"

        response = make_response(content)
        response.headers["Content-Type"] = content_type
        response.headers["Content-Disposition"] = f'attachment; filename="{username}_anime_list.{format_type}"'
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_xml(anime_list):
    """Generate XML from anime list"""
    xml_data = ['<?xml version="1.0" encoding="UTF-8"?>', "<animeList>"]
    for anime in anime_list:
        xml_data.append("  <anime>")
        xml_data.append(f"    <id>{anime.get('id')}</id>")
        xml_data.append(f"    <mediaId>{anime.get('media_id')}</mediaId>")
        xml_data.append(f"    <titleRomaji>{escape_xml(anime.get('title_romaji'))}</titleRomaji>")
        xml_data.append(f"    <status>{anime.get('status')}</status>")
        xml_data.append(f"    <score>{anime.get('score') or 0}</score>")
        xml_data.append(f"    <progress>{anime.get('progress') or 0}</progress>")
        xml_data.append("  </anime>")
    xml_data.append("</animeList>")
    return "\n".join(xml_data)

def escape_xml(text):
    """Escape XML special characters"""
    if not text:
        return ""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))

# ============================================================================
# ROUTES - AUTHENTICATION
# ============================================================================

@AnimeList_bp.route("/Anilist-auth", methods=["GET"])
def anilist_auth_base():
    """Initiate AniList OAuth flow"""
    client_id = os.environ.get("ANILIST_CLIENT_ID")
    redirect_uri = os.environ.get("ANILIST_REDIRECT_URI")
    state = request.args.get("state")

    if not client_id or not redirect_uri:
        return jsonify({"error": "Missing OAuth configuration"}), 500
    if not state:
        return jsonify({"error": "Missing state parameter"}), 400

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state
    }
    authorize_url = f"https://anilist.co/api/v2/oauth/authorize?{urlencode(params)}"
    return redirect(authorize_url)

@AnimeList_bp.route("/anilist/auth/callback", methods=["GET"])
def anilist_auth_callback():
    """Handle AniList OAuth callback"""
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state:
        return jsonify({"error": "Missing code or state"}), 400

    frontend_url = os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000")
    return redirect(f"{frontend_url}/anime-list?code={code}&state={state}")

@AnimeList_bp.route("/Anilist-exchange", methods=["POST"])
def anilist_exchange():
    """Exchange OAuth code for access token"""
    try:
        data = request.get_json()
        code = data.get("code")

        if not code:
            return jsonify({"error": "Code is required"}), 400

        # Exchange code for token
        response = requests.post("https://anilist.co/api/v2/oauth/token", json={
            "grant_type": "authorization_code",
            "client_id": os.environ.get("ANILIST_CLIENT_ID"),
            "client_secret": os.environ.get("ANILIST_CLIENT_SECRET"),
            "redirect_uri": os.environ.get("ANILIST_REDIRECT_URI"),
            "code": code
        })

        if response.status_code != 200:
            return jsonify({"error": "Token exchange failed"}), 400

        token_data = response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 31536000)

        # Get username
        user_data = query_anilist("{ Viewer { id name } }", token=access_token)
        username = user_data["Viewer"]["name"]

        # Store token
        store_anilist_token(username, access_token, refresh_token, expires_in)

        # Set cookie
        resp = make_response(jsonify({
            "message": "Authentication successful",
            "username": username
        }))
        resp.set_cookie(
            "anilist_token",
            access_token,
            max_age=expires_in,
            httponly=True,
            secure=True,
            samesite="Lax"
        )
        return resp

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@AnimeList_bp.route("/anilist/auth/check", methods=["GET"])
def check_auth():
    """Check if user is authenticated"""
    token = request.cookies.get("anilist_token")
    return jsonify({"authenticated": bool(token)}), 200

# ============================================================================
# ROUTES - MODIFY ANIME LIST
# ============================================================================

@AnimeList_bp.route("/anilist/modify", methods=["POST", "PUT", "DELETE"])
def modify_anime():
    """Modify anime list entries"""
    try:
        token = request.cookies.get("anilist_token")
        if not token:
            return jsonify({"error": "Not authenticated"}), 401

        data = request.get_json()

        # SEARCH
        if request.method == "POST" and data.get("action") == "search":
            query = data.get("query")
            result = query_anilist(SEARCH_ANIME_QUERY, {"search": query}, token)
            return jsonify({"results": result["Page"]["media"]}), 200

        # ADD
        if request.method == "POST" and data.get("action") == "add":
            mutation = """
            mutation ($mediaId: Int, $status: MediaListStatus) {
              SaveMediaListEntry(mediaId: $mediaId, status: $status) {
                id status
              }
            }
            """
            variables = {
                "mediaId": data.get("animeId"),
                "status": data.get("status", "PLANNING")
            }
            result = query_anilist(mutation, variables, token)
            return jsonify(result), 200

        # UPDATE
        if request.method == "PUT":
            mutation = """
            mutation ($mediaId: Int, $status: MediaListStatus, $progress: Int, $score: Int) {
            SaveMediaListEntry(
            mediaId: $mediaId,
            status: $status,
            progress: $progress,
            scoreRaw: $score
            ) {
            id
            status
            progress
            score
            }
            }
            """

            variables = {"mediaId": data.get("animeId")}

            if data.get("status"):
                variables["status"] = data["status"]

            if data.get("progress") is not None:
                variables["progress"] = int(data["progress"])

            if data.get("score") is not None:
                # AniList expects scoreRaw as an integer (0–1000 scale)
                variables["score"] = int(float(data["score"]) * 10)

            result = query_anilist(mutation, variables, token)
            return jsonify(result), 200


        # DELETE
        if request.method == "DELETE":
            # First get the entry ID
            query = """
            query ($mediaId: Int) {
              MediaList(mediaId: $mediaId) {
                id
              }
            }
            """
            result = query_anilist(query, {"mediaId": data.get("animeId")}, token)
            entry_id = result["MediaList"]["id"]

            mutation = """
            mutation ($id: Int) {
              DeleteMediaListEntry(id: $id) {
                deleted
              }
            }
            """
            result = query_anilist(mutation, {"id": entry_id}, token)
            return jsonify(result), 200

        # If none of the above conditions matched, return a 400 error
        return jsonify({"error": "Invalid request"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500
