import argparse
import logging
import sys

from config import load_config
from sftp_to_gcs import TransferService


def setup_logging(log_file: str = None) -> None:
    """Configures structured console and optional file logging."""
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Transfer file(s) from an SFTP server to a Google Cloud Storage (GCS) bucket."
    )
    parser.add_argument(
        "--remote-path",
        type=str,
        help="Remote file or folder path on the SFTP server (overrides SFTP_REMOTE_PATH in .env)",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        help="GCS bucket name (overrides GCS_BUCKET_NAME in .env)",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        help="GCS destination prefix/subfolder (overrides GCS_DESTINATION_PREFIX in .env)",
    )
    parser.add_argument(
        "--mode",
        choices=["stream", "temp_file"],
        help="Transfer mode: 'stream' (direct stream) or 'temp_file' (download to disk first)",
    )
    parser.add_argument(
        "--delete-remote",
        action="store_true",
        help="Delete the file from the SFTP server after successful upload",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Optional path to write logs to a file",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging(args.log_file)
    logger = logging.getLogger("main")

    logger.info("Initializing SFTP-to-GCS transfer process...")
    config = load_config()

    # Apply command-line overrides if supplied
    if args.bucket:
        config.gcs_bucket_name = args.bucket
    if args.prefix:
        prefix = args.prefix.lstrip("/")
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        config.gcs_destination_prefix = prefix
    if args.mode:
        config.transfer_mode = args.mode
    if args.delete_remote:
        config.delete_after_upload = True

    target_remote_path = args.remote_path or config.sftp_remote_path
    if not target_remote_path:
        logger.error("No remote path specified! Define SFTP_REMOTE_PATH in .env or pass --remote-path.")
        sys.exit(1)

    logger.info("Target remote SFTP path: %s", target_remote_path)
    logger.info("Target GCS Bucket: %s (Prefix: '%s')", config.gcs_bucket_name, config.gcs_destination_prefix)
    logger.info("Transfer mode: %s | Delete after upload: %s", config.transfer_mode, config.delete_after_upload)

    service = TransferService(config)

    try:
        transferred_count = service.execute(custom_remote_path=target_remote_path)
        if transferred_count > 0:
            logger.info("Transfer job completed successfully. Total files transferred: %d", transferred_count)
            sys.exit(0)
        else:
            logger.warning("No files were transferred.")
            sys.exit(0)
    except Exception as e:
        logger.critical("Transfer job encountered a fatal error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
