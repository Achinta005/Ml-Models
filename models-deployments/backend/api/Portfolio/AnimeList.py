from flask import Blueprint, jsonify, request,make_response,redirect,url_for, current_app,session
from db.config2 import get_connection
import requests
import json
from datetime import datetime
import os
import xml.etree.ElementTree as ET
import secrets
from urllib.parse import urlencode
import secrets

AnimeList_bp = Blueprint('AnimeList_bp', __name__)

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

def fetch_from_anilist(username):
    url = "https://graphql.anilist.co"
    response = requests.post(
        url,
        json={
            "query": ANILIST_QUERY,
            "variables": {"username": username}
        },
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )

    data = response.json()
    if "errors" in data:
        raise Exception(data["errors"][0].get("message", "Failed to fetch from AniList"))

    return data["data"]["MediaListCollection"]["lists"]

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anime_details (
            id INT PRIMARY KEY,
            title_romaji VARCHAR(500),
            title_english VARCHAR(500),
            title_native VARCHAR(500),
            cover_image_large VARCHAR(500),
            cover_image_medium VARCHAR(500),
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
    conn.commit()
    conn.close()

def has_data_changed(username, new_lists):
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

    cursor.execute("SELECT id, status, score, progress, updated_at FROM anime_list WHERE username = %s", (username,))
    existing_rows = cursor.fetchall()

    if len(new_entries) != len(existing_rows):
        conn.close()
        return True

    existing_map = {row["id"]: row for row in existing_rows}

    for entry in new_entries:
        ex = existing_map.get(entry["id"])
        if not ex:
            conn.close()
            return True
        if (
            ex["status"] != entry["status"] or
            ex["score"] != entry["score"] or
            ex["progress"] != entry["progress"] or
            ex["updated_at"] != entry["updatedAt"]
        ):
            conn.close()
            return True

    conn.close()
    return False

def store_in_database(username, lists):
    conn = get_connection()
    cursor = conn.cursor()
    create_tables()

    cursor.execute("DELETE FROM anime_list WHERE username = %s", (username,))

    count = 0
    for lst in lists:
        list_name = lst["name"]
        for entry in lst["entries"]:
            count += 1
            media = entry["media"]

            started_at = None
            if entry["startedAt"]["year"]:
                started_at = f"{entry['startedAt']['year']}-{entry['startedAt'].get('month',1)}-{entry['startedAt'].get('day',1)}"

            completed_at = None
            if entry["completedAt"]["year"]:
                completed_at = f"{entry['completedAt']['year']}-{entry['completedAt'].get('month',1)}-{entry['completedAt'].get('day',1)}"

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
                entry["id"], username, entry["mediaId"], list_name,
                entry["status"], entry["score"], entry["progress"],
                entry["repeat"], started_at, completed_at,
                entry["updatedAt"], entry["createdAt"]
            ))

            cursor.execute("""
                INSERT INTO anime_details (
                    id, title_romaji, title_english, title_native,
                    cover_image_large, cover_image_medium,
                    episodes, format, status, season,
                    season_year, genres, average_score, description
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    title_romaji=VALUES(title_romaji),
                    title_english=VALUES(title_english),
                    episodes=VALUES(episodes),
                    average_score=VALUES(average_score)
            """, (
                media["id"], media["title"]["romaji"], media["title"]["english"],
                media["title"]["native"], media["coverImage"]["large"],
                media["coverImage"]["medium"], media["episodes"], media["format"],
                media["status"], media["season"], media["seasonYear"],
                json.dumps(media["genres"]), media["averageScore"], media["description"]
            ))

    conn.commit()
    conn.close()
    return count

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

@AnimeList_bp.route("/anilist/BaseFunction/fetch", methods=["POST"])
def sync_anilist():
    try:
        data = request.get_json()
        username = data.get("username")

        if not username:
            return jsonify({"error": "Username is required"}), 400

        print(f"Processing AniList sync for: {username}")

        # Try AniList fetch
        lists = None
        ani_error = ""
        try:
            lists = fetch_from_anilist(username)
            fetched = True
        except Exception as e:
            fetched = False
            ani_error = str(e)
            print(f"Failed to fetch from AniList: {ani_error}")

        if not fetched:
            cached = fetch_from_database(username)
            if not cached:
                return jsonify({"error": f"No cached data found: {ani_error}"}), 500
            return jsonify({
                "success": True,
                "username": username,
                "count": len(cached),
                "animeList": cached,
                "cached": True,
                "message": "Returned cached data (AniList fetch failed)"
            }), 200

        if not has_data_changed(username, lists):
            cached = fetch_from_database(username)
            return jsonify({
                "success": True,
                "username": username,
                "count": len(cached),
                "animeList": cached,
                "cached": True,
                "message": "No changes detected, returned cached data"
            }), 200

        # Update database
        count = store_in_database(username, lists)
        anime_list = fetch_from_database(username)

        return jsonify({
            "success": True,
            "username": username,
            "count": len(anime_list),
            "animeList": anime_list,
            "cached": False,
            "message": "Data synced successfully from AniList"
        }), 200

    except Exception as e:
        print("API Error:", e)
        return jsonify({"error": str(e)}), 500


def fetch_from_export_database(username, filter_status):
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                al.*,
                ad.title_romaji,
                ad.title_english,
                ad.title_native,
                ad.cover_image_large,
                ad.cover_image_medium,
                ad.episodes,
                ad.format,
                ad.genres,
                ad.average_score,
                ad.description
            FROM anime_list al
            LEFT JOIN anime_details ad ON al.media_id = ad.id
            WHERE al.username = %s
        """
        params = [username]

        if filter_status and filter_status.upper() != "ALL":
            query += " AND al.status = %s"
            params.append(filter_status)

        query += " ORDER BY al.updated_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        for row in rows:
            if isinstance(row.get("genres"), str):
                try:
                    row["genres"] = json.loads(row["genres"])
                except json.JSONDecodeError:
                    row["genres"] = []
        return rows
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()

def generate_json(anime_list):
    return json.dumps(anime_list, indent=2, ensure_ascii=False)

def escape_xml(text):
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )

def generate_xml(anime_list):
    xml_data = ['<?xml version="1.0" encoding="UTF-8"?>', "<animeList>"]
    for anime in anime_list:
        xml_data.append("  <anime>")
        xml_data.append(f"    <id>{anime.get('id')}</id>")
        xml_data.append(f"    <mediaId>{anime.get('media_id')}</mediaId>")
        xml_data.append(f"    <username>{escape_xml(anime.get('username'))}</username>")
        xml_data.append(f"    <titleRomaji>{escape_xml(anime.get('title_romaji'))}</titleRomaji>")
        xml_data.append(f"    <titleEnglish>{escape_xml(anime.get('title_english'))}</titleEnglish>")
        xml_data.append(f"    <titleNative>{escape_xml(anime.get('title_native'))}</titleNative>")
        xml_data.append(f"    <status>{anime.get('status')}</status>")
        xml_data.append(f"    <score>{anime.get('score') or 0}</score>")
        xml_data.append(f"    <progress>{anime.get('progress') or 0}</progress>")
        xml_data.append(f"    <episodes>{anime.get('episodes') or 'N/A'}</episodes>")
        xml_data.append(f"    <format>{escape_xml(anime.get('format') or 'N/A')}</format>")
        xml_data.append(f"    <averageScore>{anime.get('average_score') or 0}</averageScore>")

        genres = anime.get("genres")
        if genres and isinstance(genres, list):
            xml_data.append("    <genres>")
            for genre in genres:
                xml_data.append(f"      <genre>{escape_xml(genre)}</genre>")
            xml_data.append("    </genres>")

        if anime.get("started_at"):
            xml_data.append(f"    <startedAt>{anime['started_at']}</startedAt>")
        if anime.get("completed_at"):
            xml_data.append(f"    <completedAt>{anime['completed_at']}</completedAt>")

        xml_data.append(f"    <coverImage>{escape_xml(anime.get('cover_image_large') or anime.get('cover_image_medium') or '')}</coverImage>")
        xml_data.append(f"    <repeatCount>{anime.get('repeat_count') or 0}</repeatCount>")
        xml_data.append(f"    <syncedAt>{anime.get('synced_at') or ''}</syncedAt>")

        if anime.get("description"):
            xml_data.append(f"    <description>{escape_xml(anime['description'])}</description>")

        xml_data.append("  </anime>")
    xml_data.append("</animeList>")
    return "\n".join(xml_data)

@AnimeList_bp.route("/anilist/BaseFunction/export", methods=["POST"])
def export_anilist():
    try:
        data = request.get_json()
        username = data.get("username")
        format_type = data.get("format", "").lower()
        filter_status = data.get("filter")

        if not username:
            return jsonify({"error": "Username is required"}), 400

        if format_type not in ["json", "xml"]:
            return jsonify({"error": "Invalid format. Must be json or xml"}), 400

        print(f"Exporting {format_type.upper()} for: {username}, filter: {filter_status or 'ALL'}")

        anime_list = fetch_from_export_database(username, filter_status)
        if not anime_list:
            return jsonify({"error": "No anime list found for this user"}), 404

        if format_type == "json":
            content = generate_json(anime_list)
            content_type = "application/json"
        else:
            content = generate_xml(anime_list)
            content_type = "application/xml"

        response = make_response(content)
        response.headers["Content-Type"] = content_type
        response.headers["Content-Disposition"] = f'attachment; filename="{username}_anime_list.{format_type}"'
        return response

    except Exception as e:
        print("Export Error:", str(e))
        return jsonify({"error": str(e) or "Internal server error"}), 500


ANILIST_API_URL = "https://graphql.anilist.co"
def get_access_token():
    """Extract AniList access token from cookies."""
    token = request.cookies.get("anilist_token")
    print("Access token:", token)
    return token

def query_anilist(query, variables=None, token=None):
    """Send a GraphQL request to AniList API."""
    try:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.post(
            ANILIST_API_URL,
            json={"query": query, "variables": variables or {}},
            headers=headers
        )

        data = response.json()

        if "errors" in data:
            print("AniList API errors:", data["errors"])
            raise Exception(data["errors"][0].get("message", "AniList API error"))

        return data["data"]

    except Exception as e:
        print("query_anilist error:", str(e))
        raise

# ---------------- DELETE: Remove Anime ---------------- #

@AnimeList_bp.route("/anilist/modify", methods=["DELETE"])
def delete_anime():
    try:
        token = request.cookies.get('anilist_token')
        if not token:
            return jsonify({"error": "Authentication required. Please connect your AniList account."}), 401

        data = request.get_json()
        anime_id = int(data.get("animeId", 0))

        if not anime_id:
            return jsonify({"error": "Anime ID is required"}), 400

        print(f"Received animeId: {anime_id}")

        # Fetch anime title by mediaId
        media_query = """
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                id
                title { romaji english }
            }
        }
        """

        media_data = query_anilist(media_query, {"id": anime_id}, token)
        if not media_data.get("Media"):
            return jsonify({"error": f"No anime found for ID {anime_id}"}), 400

        title = media_data["Media"]["title"].get("romaji") or media_data["Media"]["title"].get("english")

        # Get userId
        user_query = """query { Viewer { id } }"""
        user_data = query_anilist(user_query, {}, token)
        user_id = user_data["Viewer"]["id"]

        # Fetch user's list
        list_query = """
        query ($userId: Int) {
            MediaListCollection(userId: $userId, type: ANIME) {
                lists {
                    entries { id mediaId }
                }
            }
        }
        """
        list_data = query_anilist(list_query, {"userId": user_id}, token)
        entries = [e for l in list_data["MediaListCollection"]["lists"] for e in l["entries"]]
        entry = next((e for e in entries if e["mediaId"] == anime_id), None)

        if not entry:
            return jsonify({"error": f"Anime '{title}' not found in your list"}), 404

        entry_id = entry["id"]

        # Delete anime
        delete_mutation = """
        mutation ($id: Int) {
            DeleteMediaListEntry(id: $id) { deleted }
        }
        """
        result = query_anilist(delete_mutation, {"id": entry_id}, token)

        if not result["DeleteMediaListEntry"]["deleted"]:
            return jsonify({"error": f"Failed to delete anime '{title}'"}), 500

        return jsonify({
            "success": True,
            "message": f"Anime '{title}' removed successfully",
            "animeId": anime_id
        })

    except Exception as e:
        print("Delete error:", str(e))
        return jsonify({"error": str(e)}), 500

# ---------------- POST: Search or Add ---------------- #

@AnimeList_bp.route("/anilist/modify", methods=["POST"])
def add_or_search_anime():
    try:
        body = request.get_json()
        action = body.get("action")
        token = request.cookies.get('anilist_token')

        if action == "search":
            query_str = body.get("query", "").strip()
            if not query_str:
                return jsonify({"error": "Search query is required"}), 400

            search_query = """
            query ($search: String) {
                Page(page: 1, perPage: 10) {
                    media(search: $search, type: ANIME, sort: POPULARITY_DESC) {
                        id
                        title { romaji english native }
                        coverImage { large medium }
                        format
                        episodes
                        status
                        genres
                        averageScore
                        seasonYear
                        description
                    }
                }
            }
            """
            data = query_anilist(search_query, {"search": query_str})
            return jsonify({
                "success": True,
                "results": data["Page"]["media"]
            })

        elif action == "add":
            if not token:
                return jsonify({"error": "Authentication required"}), 401

            anime_id = body.get("animeId")
            status = body.get("status", "PLANNING").upper()

            valid_statuses = ["CURRENT", "PLANNING", "COMPLETED", "DROPPED", "PAUSED", "REPEATING"]
            if status not in valid_statuses:
                return jsonify({"error": "Invalid status value"}), 400

            mutation = """
            mutation ($mediaId: Int, $status: MediaListStatus) {
                SaveMediaListEntry(mediaId: $mediaId, status: $status) {
                    id
                    status
                    media { id title { romaji english } }
                }
            }
            """
            data = query_anilist(mutation, {"mediaId": anime_id, "status": status}, token)
            return jsonify({
                "success": True,
                "message": "Anime added successfully",
                "entry": data["SaveMediaListEntry"]
            })

        return jsonify({"error": "Invalid action. Use 'search' or 'add'"}), 400

    except Exception as e:
        print("POST error:", str(e))
        return jsonify({"error": str(e)}), 500

# ---------------- PUT: Update Anime ---------------- #

@AnimeList_bp.route("/anilist/modify", methods=["PUT"])
def update_anime():
    try:
        token = request.cookies.get('anilist_token')
        if not token:
            return jsonify({"error": "Authentication required"}), 401

        data = request.get_json()
        anime_id = data.get("animeId")
        status = data.get("status")
        progress = data.get("progress")
        score = data.get("score")

        if not anime_id:
            return jsonify({"error": "Anime ID is required"}), 400

        mutation = """
        mutation ($mediaId: Int, $status: MediaListStatus, $progress: Int, $score: Float) {
            SaveMediaListEntry(mediaId: $mediaId, status: $status, progress: $progress, score: $score) {
                id
                status
                progress
                score
                media { id title { romaji english } }
            }
        }
        """
        variables = {"mediaId": anime_id}
        if status: variables["status"] = status
        if progress is not None: variables["progress"] = progress
        if score is not None: variables["score"] = score

        result = query_anilist(mutation, variables, token)
        return jsonify({
            "success": True,
            "message": "Anime updated successfully",
            "entry": result["SaveMediaListEntry"]
        })

    except Exception as e:
        print("Update error:", str(e))
        return jsonify({"error": str(e)}), 500


@AnimeList_bp.route("/Anilist-auth", methods=["GET"])
def anilist_auth_base():
    """Initiate AniList OAuth flow with frontend-generated state"""
    client_id = os.environ.get("ANILIST_CLIENT_ID")
    redirect_uri = os.environ.get("ANILIST_REDIRECT_URI")

    if not client_id or not redirect_uri:
        return {"error": "Missing ANILIST_CLIENT_ID or ANILIST_REDIRECT_URI"}, 500

    # Get state from query param
    state = request.args.get("state")
    if not state:
        return {"error": "Missing state parameter"}, 400

    # Build AniList authorization URL
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

    frontend_url = os.getenv("NEXT_PUBLIC_FRONTEND_URL")
    if not frontend_url:
        return jsonify({"error": "Frontend URL not configured"}), 500

    # Redirect to frontend with code and state in query params
    return redirect(f"{frontend_url}/anime-list?code={code}&state={state}")


@AnimeList_bp.route('/anilist/auth/check', methods=['GET'])
def check_auth():
    """Check if user is authenticated"""
    try:
        token = request.cookies.get('anilist_token')
        
        print(f"🔍 Auth check - Token present: {bool(token)}")
        print(f"🔍 All cookies: {list(request.cookies.keys())}")
        
        return jsonify({"authenticated": bool(token)}), 200

    except Exception as e:
        print(f"❌ Error checking authentication: {e}")
        return jsonify({
            "error": "Failed to check authentication",
            "message": str(e)
        }), 500

       
@AnimeList_bp.route("/Anilist-exchange", methods=["POST"])
def anilist_exchange():
    """Exchange AniList OAuth code for access token"""
    data = request.json
    if not data or "code" not in data:
        return jsonify({"error": "Missing code"}), 400
    code = data.get("code")

    if not code:
        return jsonify({"error": "Missing code"}), 400

    client_id = os.environ.get("ANILIST_CLIENT_ID")
    client_secret = os.environ.get("ANILIST_CLIENT_SECRET")
    redirect_uri = os.environ.get("ANILIST_REDIRECT_URI")

    try:
        token_response = requests.post(
            "https://anilist.co/api/v2/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        token_response.raise_for_status()
        token_data = token_response.json()

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 31536000)

        # Set cookies
        frontend_url = os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000")
        response = make_response(jsonify({"success": True}))
        response.set_cookie(
            "anilist_token",
            access_token,
            max_age=expires_in,
            httponly=True,
            samesite="Lax",
        )
        if refresh_token:
            response.set_cookie(
                "anilist_refresh",
                refresh_token,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="Lax",
            )

        return response

    except requests.RequestException as err:
        current_app.logger.error(f"AniList Token Exchange Error: {err}")
        return jsonify({"error": "Token exchange failed", "details": str(err)}), 500
