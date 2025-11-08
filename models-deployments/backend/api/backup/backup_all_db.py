from flask import Blueprint, jsonify
import os
import subprocess
import tempfile
import zipfile
import datetime
import shutil
import pickle
import json
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

# Create Blueprint
backup_blueprint = Blueprint('backup', __name__)

# Load environment variables
TIDB_HOST = os.getenv("MYSQL_HOST")
TIDB_USER = os.getenv("MYSQL_USER")
TIDB_PASSWORD = os.getenv("MYSQL_PASSWORD")
GOOGLE_FOLDER_ID = os.getenv("GOOGLE_FOLDER_ID", "")

# OAuth setup
SCOPES = ['https://www.googleapis.com/auth/drive.file']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'


def get_credentials_file():
    """Get credentials from environment variable or file"""
    # Check if credentials exist as environment variable
    google_creds = os.getenv('GOOGLE_CREDENTIALS')
    
    if google_creds:
        # Create temporary credentials file from environment variable
        temp_creds_path = '/tmp/credentials.json'
        with open(temp_creds_path, 'w') as f:
            f.write(google_creds)
        return temp_creds_path
    
    # Fall back to local file (for development)
    if os.path.exists(CREDENTIALS_FILE):
        return CREDENTIALS_FILE
    
    raise Exception(
        "No credentials found. Set GOOGLE_CREDENTIALS environment variable "
        "or add credentials.json file."
    )


def get_drive_service():
    """Authenticate and return Google Drive service"""
    creds = None
    
    # Check for existing token
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials_path = get_credentials_file()
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES)
            creds = flow.run_local_server(port=8080)
        
        # Save credentials for next run
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('drive', 'v3', credentials=creds)


@backup_blueprint.route('/authenticate-drive', methods=['GET', 'POST'])
def authenticate_drive():
    """One-time authentication endpoint"""
    try:
        print("Authenticating with Google Drive...")
        drive_service = get_drive_service()
        about = drive_service.about().get(fields="user, storageQuota").execute()
        
        return jsonify({
            "status": "success",
            "message": "Google Drive authenticated successfully!",
            "user": about.get('user', {}).get('emailAddress'),
            "storage_used_mb": round(int(about.get('storageQuota', {}).get('usage', 0)) / (1024*1024), 2),
            "storage_limit_mb": round(int(about.get('storageQuota', {}).get('limit', 0)) / (1024*1024), 2)
        })
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@backup_blueprint.route('/backup-all-db', methods=['GET', 'POST'])
def backup_all_databases():
    """Main backup function"""
    print("Backup TiDB/MySQL Hit...")
    temp_dir = tempfile.mkdtemp()
    sql_file_path = os.path.join(temp_dir, "all_databases_backup.sql")
    zip_path = os.path.join(temp_dir, "all_databases_backup.zip")
    config_file = os.path.join(temp_dir, "my.cnf")

    try:
        print("Authenticating with Google Drive...")
        drive_service = get_drive_service()
        
        print("Creating MySQL config file...")
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

        print(f"Running mysqldump with timeout (10 minutes)...")
        
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
                    raise subprocess.CalledProcessError(
                        process.returncode, dump_cmd, stderr=stderr_output
                    )
                    
                if stderr_output:
                    print(f"mysqldump warnings: {stderr_output}")
                    
            except subprocess.TimeoutExpired:
                process.kill()
                raise Exception("mysqldump timeout after 10 minutes.")
        
        print("Databases dumped successfully.")

        if not os.path.exists(sql_file_path):
            raise Exception("SQL backup file was not created")
        
        file_size = os.path.getsize(sql_file_path)
        if file_size == 0:
            raise Exception("SQL backup file is empty")
        
        print(f"Backup file size: {file_size / (1024*1024):.2f} MB")

        print("Zipping backup...")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(sql_file_path, arcname="all_databases_backup.sql")
        print("Backup zipped successfully.")

        print("Deleting old backups from Google Drive...")
        try:
            query = "trashed=false and mimeType='application/zip' and name contains 'TIDB_Backup_'"
            if GOOGLE_FOLDER_ID:
                query = f"'{GOOGLE_FOLDER_ID}' in parents and " + query
            
            results = drive_service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=100
            ).execute()
            
            for file in results.get("files", []):
                print(f"  Deleting: {file['name']}")
                drive_service.files().delete(fileId=file["id"]).execute()
        except HttpError as e:
            print(f"Warning: Could not delete old backups: {e}")

        print("Uploading to Google Drive...")
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_metadata = {
            "name": f"TIDB_Backup_{timestamp}.zip"
        }
        
        if GOOGLE_FOLDER_ID:
            file_metadata["parents"] = [GOOGLE_FOLDER_ID]
        
        media = MediaFileUpload(zip_path, mimetype="application/zip", resumable=True)
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink"
        ).execute()

        print(f"✅ Backup uploaded: {uploaded_file['name']}")
        return jsonify({
            "status": "success",
            "file_id": uploaded_file.get("id"),
            "file_name": uploaded_file.get("name"),
            "web_link": uploaded_file.get("webViewLink"),
            "size_mb": f"{file_size / (1024*1024):.2f}"
        })

    except subprocess.CalledProcessError as e:
        error_msg = f"Database backup failed: {e.stderr if e.stderr else str(e)}"
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg}), 500
    except HttpError as e:
        error_msg = f"Google Drive error: {str(e)}"
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg, "type": "google_drive_error"}), 500
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        print("Cleaning up temporary files...")
        shutil.rmtree(temp_dir, ignore_errors=True)