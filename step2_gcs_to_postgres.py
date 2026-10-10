#!/usr/bin/env python3
"""
Step 2: Google Cloud Storage (GCS) to Cloud SQL (PostgreSQL)
Streams CSV file directly from GCS into PostgreSQL staging table using native bulk COPY.
"""

import argparse
import datetime
import logging
import sys
import psycopg2
from google.cloud import storage

from config import load_config

logger = logging.getLogger("step2_gcs_to_postgres")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [Step 2: GCS->Postgres] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_latest_blob(bucket: storage.Bucket, prefix: str) -> storage.Blob:
    """Finds the most recently updated blob under the given prefix."""
    blobs = list(bucket.list_blobs(prefix=prefix))
    if not blobs:
        return None
    # Sort by updated timestamp descending
    blobs.sort(key=lambda b: b.updated, reverse=True)
    return blobs[0]


def run_step2(blob_name: str = None) -> bool:
    """Executes Step 2: Ingest from GCS to PostgreSQL."""
    config = load_config()

    if not config.db_host or not config.db_user or not config.db_name:
        logger.error("Missing database configuration (DB_HOST, DB_USER, DB_NAME in .env).")
        return False

    logger.info("Initializing GCS Client...")
    gcs_client = storage.Client(project=config.gcp_project_id) if config.gcp_project_id else storage.Client()
    bucket = gcs_client.bucket(config.gcs_bucket_name)

    # Determine target blob to load
    target_blob = None
    if blob_name:
        target_blob = bucket.blob(blob_name)
        if not target_blob.exists():
            logger.error("Specified GCS blob gs://%s/%s does not exist.", config.gcs_bucket_name, blob_name)
            return False
    else:
        logger.info("Looking for the latest file in bucket gs://%s under prefix '%s'...",
                    config.gcs_bucket_name, config.gcs_destination_prefix)
        target_blob = get_latest_blob(bucket, config.gcs_destination_prefix)
        if not target_blob:
            logger.error("No blobs found in bucket gs://%s under prefix '%s'.",
                         config.gcs_bucket_name, config.gcs_destination_prefix)
            return False

    logger.info("Selected GCS Blob: gs://%s/%s (Size: %.2f KB)",
                config.gcs_bucket_name, target_blob.name, (target_blob.size or 0) / 1024)

    logger.info("Connecting to Cloud SQL PostgreSQL at %s:%d (Database: %s)...",
                config.db_host, config.db_port, config.db_name)

    conn_params = {
        "host": config.db_host,
        "port": config.db_port,
        "dbname": config.db_name,
        "user": config.db_user,
        "sslmode": config.db_sslmode,
    }
    if config.db_password:
        conn_params["password"] = config.db_password

    conn = None
    try:
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = False
        cursor = conn.cursor()

        # Step A: Ensure staging table exists or truncate it
        staging_table = config.db_staging_table
        logger.info("Truncating staging table '%s'...", staging_table)
        cursor.execute(f"TRUNCATE TABLE {staging_table};")

        # Step B: Stream directly from GCS blob and COPY into PostgreSQL
        logger.info("Streaming CSV from GCS directly into PostgreSQL table '%s'...", staging_table)
        with target_blob.open("r", encoding="utf-8") as gcs_stream:
            copy_sql = f"COPY {staging_table} FROM STDIN WITH (FORMAT csv, HEADER true);"
            cursor.copy_expert(copy_sql, gcs_stream)

        # Step C: Verify loaded rows
        cursor.execute(f"SELECT COUNT(*) FROM {staging_table};")
        row_count = cursor.fetchone()[0]
        conn.commit()

        logger.info("Step 2 completed successfully! Ingested %d rows into '%s'.", row_count, staging_table)
        cursor.close()
        return True

    except Exception as e:
        logger.error("Step 2 failed during PostgreSQL ingestion: %s", e, exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")


def main():
    parser = argparse.ArgumentParser(description="Step 2: Stream CSV from GCS to Cloud SQL PostgreSQL.")
    parser.add_argument("--blob-name", type=str, help="Specific GCS blob name to ingest (defaults to latest)")
    args = parser.parse_args()

    setup_logging()
    success = run_step2(blob_name=args.blob_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
