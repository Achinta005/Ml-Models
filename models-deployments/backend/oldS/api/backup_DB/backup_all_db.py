from flask import Blueprint, jsonify
import os
import subprocess
import tempfile
import zipfile
import datetime
import shutil
import logging
from b2sdk.v1 import InMemoryAccountInfo, B2Api
from dotenv import load_dotenv

load_dotenv()

backup_blueprint = Blueprint("backup", __name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TIDB_HOST = os.getenv("TIDB_HOST")
TIDB_USER = os.getenv("TIDB_USER")
TIDB_PASSWORD = os.getenv("TIDB_PASSWORD")
B2_ACCOUNT_ID = os.getenv("B2_ACCOUNT_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")


def get_b2_bucket():
    """Authenticate and return the B2 bucket."""
    if not B2_BUCKET_NAME or not B2_ACCOUNT_ID or not B2_APPLICATION_KEY:
        logger.error("B2 credentials or bucket name are not properly set in environment variables")
        raise ValueError("B2 credentials or bucket name are not properly set in environment variables")

    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    try:
        b2_api.authorize_account("production", B2_ACCOUNT_ID, B2_APPLICATION_KEY)
        logger.info("✅ B2 authorization successful")
    except Exception as e:
        logger.error("❌ B2 authorization failed: %s", e)
        raise

    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
    if not bucket:
        logger.error("❌ Bucket '%s' not found", B2_BUCKET_NAME)
        raise Exception(f"Bucket '{B2_BUCKET_NAME}' not found")
    
    logger.info("✅ B2 bucket '%s' found", B2_BUCKET_NAME)
    return bucket


@backup_blueprint.route("/backup-all-db", methods=["GET"])
def backup_all_databases():
    temp_dir = tempfile.mkdtemp()
    sql_file_path = os.path.join(temp_dir, "all_databases_backup.sql")
    zip_path = os.path.join(temp_dir, "all_databases_backup.zip")
    config_file = os.path.join(temp_dir, "my.cnf")

    try:
        logger.info("Starting backup for host: %s", TIDB_HOST)

        with open(config_file, "w") as f:
            f.write("[client]\n")
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
            "--column-statistics=0",
        ]

        logger.info("Running mysqldump command")
        with open(sql_file_path, "w") as outfile:
            process = subprocess.Popen(dump_cmd, stdout=outfile, stderr=subprocess.PIPE, text=True)
            _, stderr_output = process.communicate(timeout=600)
            if process.returncode != 0:
                logger.error("mysqldump failed: %s", stderr_output)
                raise subprocess.CalledProcessError(process.returncode, dump_cmd, stderr_output)
            if stderr_output:
                logger.warning("mysqldump warnings: %s", stderr_output)

        logger.info("Zipping the SQL backup")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(sql_file_path, arcname="all_databases_backup.sql")

        bucket = get_b2_bucket()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        b2_file_name = f"TIDB_Backup_{timestamp}.zip"

        logger.info("Uploading backup to B2 as %s", b2_file_name)
        with open(zip_path, "rb") as f:
            bucket.upload_bytes(f.read(), b2_file_name)

        backup_size_mb = os.path.getsize(sql_file_path) / (1024 * 1024)
        logger.info("Backup successful, size: %.2f MB", backup_size_mb)

        return jsonify({
            "status": "success",
            "file_name": b2_file_name,
            "size_mb": f"{backup_size_mb:.2f}"
        })

    except subprocess.CalledProcessError as e:
        logger.error("Database backup failed: %s", e.stderr if e.stderr else str(e))
        return jsonify({"status": "error", "message": e.stderr if e.stderr else str(e)}), 500
    except Exception as e:
        logger.exception("Unexpected error during backup")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        logger.info("Cleaning up temporary files")
        shutil.rmtree(temp_dir, ignore_errors=True)
