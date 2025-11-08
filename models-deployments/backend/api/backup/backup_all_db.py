from flask import Blueprint, jsonify
import os
import subprocess
import tempfile
import zipfile
import datetime
import shutil
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

backup_blueprint = Blueprint('backup', __name__)

# Load environment variables
TIDB_HOST = os.getenv("MYSQL_HOST")
TIDB_USER = os.getenv("MYSQL_USER")
TIDB_PASSWORD = os.getenv("MYSQL_PASSWORD")
GOOGLE_FOLDER_ID = os.getenv("GOOGLE_FOLDER_ID", "")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")
TOKEN_FILE = "token.pickle"
CREDENTIALS_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/drive.file']


def get_drive_service():
    """Dual-mode authentication: service account or local token.pickle"""
    # 1️⃣ Use service account if available (server/headless)
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        return build("drive", "v3", credentials=creds)

    # 2️⃣ Fallback to user OAuth (token.pickle) for local dev
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise Exception("No credentials found for OAuth flow.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)

    return build("drive", "v3", credentials=creds)


@backup_blueprint.route('/backup-all-db', methods=['GET', 'POST'])
def backup_all_databases():
    """Backup TiDB/MySQL to Google Drive (dual-mode auth)"""
    temp_dir = tempfile.mkdtemp()
    sql_file_path = os.path.join(temp_dir, "all_databases_backup.sql")
    zip_path = os.path.join(temp_dir, "all_databases_backup.zip")
    config_file = os.path.join(temp_dir, "my.cnf")

    try:
        print("Authenticating with Google Drive...")
        drive_service = get_drive_service()

        # Create temporary MySQL config file
        with open(config_file, "w") as f:
            f.write(f"[client]\n")
            f.write(f"host={TIDB_HOST}\n")
            f.write(f"user={TIDB_USER}\n")
            f.write(f"password={TIDB_PASSWORD}\n")

        dump_cmd = [
            "mysqldump",
            f"--defaults-file={config_file}",
            "--all-databases",
            "--quick",
            "--skip-lock-tables",
            "--no-tablespaces",
            "--set-gtid-purged=OFF",
            "--column-statistics=0"
        ]

        print(f"Running mysqldump...")
        with open(sql_file_path, "w") as outfile:
            process = subprocess.Popen(
                dump_cmd,
                stdout=outfile,
                stderr=subprocess.PIPE,
                text=True
            )
            try:
                stderr_output = process.communicate(timeout=600)[1]
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, dump_cmd, stderr=stderr_output)
                if stderr_output:
                    print(f"mysqldump warnings: {stderr_output}")
            except subprocess.TimeoutExpired:
                process.kill()
                raise Exception("mysqldump timeout after 10 minutes.")

        if not os.path.exists(sql_file_path) or os.path.getsize(sql_file_path) == 0:
            raise Exception("SQL backup file was not created or is empty.")

        # Zip the SQL file
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(sql_file_path, arcname="all_databases_backup.sql")

        # Delete old backups from Drive
        try:
            query = "trashed=false and mimeType='application/zip' and name contains 'TIDB_Backup_'"
            if GOOGLE_FOLDER_ID:
                query = f"'{GOOGLE_FOLDER_ID}' in parents and " + query

            results = drive_service.files().list(q=query, fields="files(id, name)", pageSize=100).execute()
            for file in results.get("files", []):
                print(f"Deleting old backup: {file['name']}")
                drive_service.files().delete(fileId=file["id"]).execute()
        except HttpError as e:
            print(f"Warning: Could not delete old backups: {e}")

        # Upload new backup
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_metadata = {"name": f"TIDB_Backup_{timestamp}.zip"}
        if GOOGLE_FOLDER_ID:
            file_metadata["parents"] = [GOOGLE_FOLDER_ID]

        media = MediaFileUpload(zip_path, mimetype="application/zip", resumable=True)
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink"
        ).execute()

        return jsonify({
            "status": "success",
            "file_id": uploaded_file.get("id"),
            "file_name": uploaded_file.get("name"),
            "web_link": uploaded_file.get("webViewLink"),
            "size_mb": f"{os.path.getsize(sql_file_path)/(1024*1024):.2f}"
        })

    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": e.stderr if e.stderr else str(e)}), 500
    except HttpError as e:
        return jsonify({"status": "error", "message": str(e), "type": "google_drive_error"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
