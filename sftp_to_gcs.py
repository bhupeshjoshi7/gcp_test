import logging
import os
import stat
import time
from typing import List, Tuple
import paramiko
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from config import AppConfig

logger = logging.getLogger("sftp_to_gcs")


class SFTPHandler:
    """Manages SSH and SFTP connections and remote file operations."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.ssh_client: paramiko.SSHClient = None
        self.sftp_client: paramiko.SFTPClient = None

    def connect(self) -> None:
        """Establishes SSH and SFTP connection."""
        logger.info("Connecting to SFTP server %s:%d as %s...", self.config.sftp_host, self.config.sftp_port, self.config.sftp_user)
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": self.config.sftp_host,
            "port": self.config.sftp_port,
            "username": self.config.sftp_user,
            "timeout": 30,
            "banner_timeout": 30,
        }

        if self.config.sftp_key_path:
            key_path = os.path.expanduser(self.config.sftp_key_path)
            connect_kwargs["key_filename"] = key_path
            connect_kwargs["look_for_keys"] = False
            connect_kwargs["allow_agent"] = False
            if self.config.sftp_key_passphrase:
                connect_kwargs["passphrase"] = self.config.sftp_key_passphrase
        elif self.config.sftp_password:
            connect_kwargs["password"] = self.config.sftp_password
            connect_kwargs["look_for_keys"] = False
            connect_kwargs["allow_agent"] = False

        try:
            self.ssh_client.connect(**connect_kwargs)
            self.sftp_client = self.ssh_client.open_sftp()
            logger.info("Successfully connected to SFTP server.")
        except Exception as e:
            logger.error("Failed to connect to SFTP server %s: %s", self.config.sftp_host, e)
            self.close()
            raise

    def get_path_info(self, remote_path: str) -> Tuple[bool, int]:
        """
        Returns (is_dir, size_bytes).
        Raises FileNotFoundError if remote path does not exist.
        """
        try:
            remote_stat = self.sftp_client.stat(remote_path)
            is_directory = stat.S_ISDIR(remote_stat.st_mode)
            return is_directory, remote_stat.st_size
        except IOError as e:
            raise FileNotFoundError(f"Remote SFTP path not found or inaccessible: {remote_path} (Error: {e})")

    def list_files(self, remote_path: str) -> List[Tuple[str, int]]:
        """
        If remote_path is a directory, returns a list of (file_path, file_size) for regular files.
        If it's a file, returns a list with only this file.
        """
        is_dir, size = self.get_path_info(remote_path)
        if not is_dir:
            return [(remote_path, size)]

        results = []
        for item in self.sftp_client.listdir_attr(remote_path):
            if not stat.S_ISDIR(item.st_mode):
                item_full_path = remote_path.rstrip("/") + "/" + item.filename
                results.append((item_full_path, item.st_size))
        return results

    def open_read_stream(self, remote_path: str):
        """Opens a remote file stream for binary reading."""
        # Using a 256KB buffer for optimal transfer speeds over network
        return self.sftp_client.open(remote_path, mode="rb", bufsize=262144)

    def download_to_local(self, remote_path: str, local_path: str) -> None:
        """Downloads a remote file directly to a local temporary path."""
        logger.info("Downloading SFTP file [%s] -> local [%s]...", remote_path, local_path)
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        self.sftp_client.get(remote_path, local_path)

    def delete_remote_file(self, remote_path: str) -> None:
        """Deletes a file from the SFTP server."""
        logger.info("Removing remote SFTP file: %s", remote_path)
        self.sftp_client.remove(remote_path)

    def close(self) -> None:
        """Closes SFTP and SSH clients safely."""
        if self.sftp_client:
            try:
                self.sftp_client.close()
            except Exception:
                pass
            self.sftp_client = None

        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass
            self.ssh_client = None


class GCSHandler:
    """Manages Google Cloud Storage client and uploads."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.client: storage.Client = None
        self.bucket: storage.Bucket = None

    def initialize(self) -> None:
        """Initializes GCS client and verifies bucket access."""
        logger.info("Initializing Google Cloud Storage client (Bucket: %s)...", self.config.gcs_bucket_name)
        client_kwargs = {}
        if self.config.gcp_project_id:
            client_kwargs["project"] = self.config.gcp_project_id

        try:
            self.client = storage.Client(**client_kwargs)
            self.bucket = self.client.bucket(self.config.gcs_bucket_name)
            logger.info("Configured GCS Bucket '%s'.", self.config.gcs_bucket_name)
        except GoogleCloudError as e:
            logger.error("GCS authorization or network error: %s", e)
            raise
        except Exception as e:
            logger.error("Failed to initialize GCS client: %s", e)
            raise

    def get_destination_blob_name(self, remote_file_path: str) -> str:
        """Constructs destination blob name from file name and configured prefix."""
        filename = os.path.basename(remote_file_path.rstrip("/"))
        prefix = self.config.gcs_destination_prefix
        return f"{prefix}{filename}"

    def upload_stream(self, file_stream, destination_blob_name: str, expected_size: int) -> None:
        """Uploads directly from a readable stream to GCS blob."""
        blob = self.bucket.blob(destination_blob_name)
        logger.info("Streaming upload to gs://%s/%s (Size: %.2f MB)...",
                    self.config.gcs_bucket_name, destination_blob_name, expected_size / (1024 * 1024))
        
        # Rewind stream to beginning if needed
        if hasattr(file_stream, "seek"):
            file_stream.seek(0)
            
        blob.upload_from_file(file_stream, size=expected_size, rewind=True)

        # Verification
        blob.reload()
        if blob.size != expected_size:
            raise IOError(f"Uploaded blob size ({blob.size} bytes) does not match expected size ({expected_size} bytes)!")

    def upload_file(self, local_file_path: str, destination_blob_name: str, expected_size: int) -> None:
        """Uploads a local file to GCS blob."""
        blob = self.bucket.blob(destination_blob_name)
        logger.info("Uploading local file to gs://%s/%s...", self.config.gcs_bucket_name, destination_blob_name)
        blob.upload_from_filename(local_file_path)

        blob.reload()
        if blob.size != expected_size:
            raise IOError(f"Uploaded blob size ({blob.size} bytes) does not match expected size ({expected_size} bytes)!")


class TransferService:
    """Orchestrates transferring files from SFTP to GCS."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.sftp_handler = SFTPHandler(config)
        self.gcs_handler = GCSHandler(config)

    def transfer_single_file(self, remote_file_path: str, file_size: int) -> bool:
        """Transfers one file from SFTP to GCS."""
        destination_blob_name = self.gcs_handler.get_destination_blob_name(remote_file_path)
        start_time = time.time()
        logger.info("Starting transfer: [%s] -> [gs://%s/%s]",
                    remote_file_path, self.config.gcs_bucket_name, destination_blob_name)

        try:
            if self.config.transfer_mode == "stream":
                with self.sftp_handler.open_read_stream(remote_file_path) as stream:
                    self.gcs_handler.upload_stream(stream, destination_blob_name, file_size)
            else:
                # Temporary file mode
                filename = os.path.basename(remote_file_path)
                local_temp_file = os.path.join(self.config.temp_dir, f"sftp_sync_{int(time.time())}_{filename}")
                try:
                    self.sftp_handler.download_to_local(remote_file_path, local_temp_file)
                    self.gcs_handler.upload_file(local_temp_file, destination_blob_name, file_size)
                finally:
                    if os.path.exists(local_temp_file):
                        try:
                            os.remove(local_temp_file)
                        except Exception as e:
                            logger.warning("Could not delete local temp file %s: %s", local_temp_file, e)

            elapsed_time = time.time() - start_time
            speed_mb_s = (file_size / (1024 * 1024)) / elapsed_time if elapsed_time > 0 else 0
            logger.info("Upload completed successfully in %.2f seconds (%.2f MB/s).", elapsed_time, speed_mb_s)

            if self.config.delete_after_upload:
                self.sftp_handler.delete_remote_file(remote_file_path)
                logger.info("Deleted remote source file: %s", remote_file_path)

            return True

        except Exception as e:
            logger.error("Failed to transfer file %s: %s", remote_file_path, e, exc_info=True)
            return False

    def execute(self, custom_remote_path: str = None) -> int:
        """
        Executes the file transfer job.
        Returns the count of successfully transferred files.
        """
        target_path = custom_remote_path or self.config.sftp_remote_path
        if not target_path:
            raise ValueError("No remote path specified. Provide SFTP_REMOTE_PATH in .env or pass as argument.")

        self.sftp_handler.connect()
        try:
            self.gcs_handler.initialize()
            files_to_transfer = self.sftp_handler.list_files(target_path)
            
            if not files_to_transfer:
                logger.warning("No files found at remote path: %s", target_path)
                return 0

            logger.info("Found %d file(s) to transfer.", len(files_to_transfer))
            successful_count = 0

            for remote_path, size in files_to_transfer:
                success = self.transfer_single_file(remote_path, size)
                if success:
                    successful_count += 1
                else:
                    logger.error("Aborting subsequent transfers due to error on file: %s", remote_path)
                    break

            logger.info("Transfer job finished. %d of %d files transferred successfully.",
                        successful_count, len(files_to_transfer))
            return successful_count

        finally:
            self.sftp_handler.close()
