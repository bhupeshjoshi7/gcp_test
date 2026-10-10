#!/usr/bin/env python3
"""
Step 1: SFTP (Argon) to Google Cloud Storage (GCS)
Fetches source file from remote SFTP server and streams it into GCS bucket.
"""

import argparse
import datetime
import logging
import sys

from config import load_config
from sftp_to_gcs import TransferService

logger = logging.getLogger("step1_sftp_to_gcs")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [Step 1: SFTP->GCS] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_step1(custom_prefix: str = None, remote_path: str = None) -> bool:
    """Executes Step 1: Argon SFTP to GCS transfer."""
    config = load_config()

    # Optional date-based subfolder partitioning: e.g., incoming/2026-10-10/
    if custom_prefix:
        config.gcs_destination_prefix = custom_prefix
    else:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        # Ensure prefix ends with date subfolder if default
        if config.gcs_destination_prefix and not config.gcs_destination_prefix.endswith(f"{today_str}/"):
            config.gcs_destination_prefix = f"{config.gcs_destination_prefix.rstrip('/')}/{today_str}/"

    target_path = remote_path or config.sftp_remote_path
    logger.info("Starting Step 1: Fetching from SFTP [%s] -> GCS [gs://%s/%s]...",
                target_path, config.gcs_bucket_name, config.gcs_destination_prefix)

    service = TransferService(config)
    try:
        count = service.execute(custom_remote_path=target_path)
        if count > 0:
            logger.info("Step 1 finished successfully! Transferred %d file(s).", count)
            return True
        else:
            logger.warning("Step 1 finished with 0 files transferred.")
            return False
    except Exception as e:
        logger.error("Step 1 failed with error: %s", e, exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(description="Step 1: Pull from Argon SFTP and push to GCS.")
    parser.add_argument("--remote-path", type=str, help="Override remote SFTP file path")
    parser.add_argument("--prefix", type=str, help="Override GCS destination prefix")
    args = parser.parse_args()

    setup_logging()
    success = run_step1(custom_prefix=args.prefix, remote_path=args.remote_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
