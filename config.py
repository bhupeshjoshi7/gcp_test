import os
import sys
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


@dataclass
class AppConfig:
    # SFTP Settings
    sftp_host: str
    sftp_port: int
    sftp_user: str
    sftp_password: Optional[str]
    sftp_key_path: Optional[str]
    sftp_key_passphrase: Optional[str]
    sftp_remote_path: str

    # GCS Settings
    gcs_bucket_name: str
    gcs_destination_prefix: str
    gcp_project_id: Optional[str]
    google_application_credentials: Optional[str]

    # Transfer Options
    transfer_mode: str  # 'stream' or 'temp_file'
    delete_after_upload: bool
    temp_dir: str

    # Cloud SQL PostgreSQL Settings
    db_host: Optional[str] = None
    db_port: int = 5432
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    db_staging_table: str = "staging_argon_data"
    db_prod_table: str = "argon_data"
    db_sslmode: str = "prefer"


def load_config() -> AppConfig:
    """Loads and validates configuration from environment variables."""
    sftp_host = os.getenv("SFTP_HOST", "").strip()
    sftp_port_str = os.getenv("SFTP_PORT", "22").strip()
    sftp_user = os.getenv("SFTP_USER", "").strip()
    sftp_password = os.getenv("SFTP_PASSWORD", "").strip() or None
    sftp_key_path = os.getenv("SFTP_KEY_PATH", "").strip() or None
    if sftp_key_path:
        sftp_key_path = os.path.expanduser(sftp_key_path)
    sftp_key_passphrase = os.getenv("SFTP_KEY_PASSPHRASE", "").strip() or None
    sftp_remote_path = os.getenv("SFTP_REMOTE_PATH", "").strip()

    gcs_bucket_name = os.getenv("GCS_BUCKET_NAME", "").strip()
    gcs_destination_prefix = os.getenv("GCS_DESTINATION_PREFIX", "").strip()
    gcp_project_id = os.getenv("GCP_PROJECT_ID", "").strip() or None
    google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip() or None

    transfer_mode = os.getenv("TRANSFER_MODE", "stream").strip().lower()
    delete_after_upload_str = os.getenv("DELETE_AFTER_UPLOAD", "false").strip().lower()
    delete_after_upload = delete_after_upload_str in ("1", "true", "yes")
    temp_dir = os.getenv("TEMP_DIR", "/tmp").strip()

    # Cloud SQL PostgreSQL settings
    db_host = os.getenv("DB_HOST", "").strip() or None
    db_port_str = os.getenv("DB_PORT", "5432").strip()
    db_name = os.getenv("DB_NAME", "").strip() or None
    db_user = os.getenv("DB_USER", "").strip() or None
    db_password = os.getenv("DB_PASSWORD", "").strip() or None
    db_staging_table = os.getenv("DB_STAGING_TABLE", "staging_argon_data").strip()
    db_prod_table = os.getenv("DB_PROD_TABLE", "argon_data").strip()
    db_sslmode = os.getenv("DB_SSLMODE", "prefer").strip()

    try:
        db_port = int(db_port_str)
    except ValueError:
        db_port = 5432

    # Validations
    errors = []
    if not sftp_host:
        errors.append("SFTP_HOST is required.")
    if not sftp_user:
        errors.append("SFTP_USER is required.")
    if not sftp_password and not sftp_key_path:
        errors.append("Either SFTP_PASSWORD or SFTP_KEY_PATH must be provided.")
    if not gcs_bucket_name:
        errors.append("GCS_BUCKET_NAME is required.")

    try:
        sftp_port = int(sftp_port_str)
    except ValueError:
        errors.append(f"SFTP_PORT must be a valid integer, got '{sftp_port_str}'.")
        sftp_port = 22

    if transfer_mode not in ("stream", "temp_file"):
        errors.append(f"TRANSFER_MODE must be either 'stream' or 'temp_file', got '{transfer_mode}'.")

    if errors:
        sys.stderr.write("\n[CONFIGURATION ERROR]\n")
        for err in errors:
            sys.stderr.write(f"  - {err}\n")
        sys.stderr.write("\nPlease check your .env file or environment variables.\n\n")
        sys.exit(1)

    # Normalize destination prefix
    if gcs_destination_prefix.startswith("/"):
        gcs_destination_prefix = gcs_destination_prefix.lstrip("/")
    if gcs_destination_prefix and not gcs_destination_prefix.endswith("/"):
        gcs_destination_prefix += "/"

    return AppConfig(
        sftp_host=sftp_host,
        sftp_port=sftp_port,
        sftp_user=sftp_user,
        sftp_password=sftp_password,
        sftp_key_path=sftp_key_path,
        sftp_key_passphrase=sftp_key_passphrase,
        sftp_remote_path=sftp_remote_path,
        gcs_bucket_name=gcs_bucket_name,
        gcs_destination_prefix=gcs_destination_prefix,
        gcp_project_id=gcp_project_id,
        google_application_credentials=google_creds,
        transfer_mode=transfer_mode,
        delete_after_upload=delete_after_upload,
        temp_dir=temp_dir,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        db_staging_table=db_staging_table,
        db_prod_table=db_prod_table,
        db_sslmode=db_sslmode,
    )
