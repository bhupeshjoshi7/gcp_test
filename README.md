# SFTP to Google Cloud Storage (GCS) Transfer Pipeline

A robust, production-ready Python tool to transfer files from a remote SFTP server directly into a Google Cloud Storage bucket. Designed to run seamlessly on a Google Cloud Platform (GCP) Compute Engine VM.

---

## 📁 Project Structure

```text
├── .env.example              # Template for credentials & config
├── .gitignore                # Protects secrets, venvs, and logs from Git
├── requirements.txt          # Python dependencies (google-cloud-storage, paramiko, python-dotenv)
├── config.py                 # Environment loader & configuration validation
├── sftp_to_gcs.py            # Core SFTP & GCS handler logic (streaming and temp file modes)
├── main.py                   # CLI entrypoint with logging and argument parsing
├── setup.sh                  # One-click VM setup script
├── systemd/
│   ├── sftp-to-gcs.service   # Systemd service unit (for automated background runs)
│   └── sftp-to-gcs.timer     # Systemd timer unit (for periodic scheduled runs)
└── README.md
```

---

## ⚙️ Key Features

- **Direct Stream Upload (`stream`)**: Stream files directly from SFTP into GCS without writing to local VM disk (ideal for large files and memory efficiency).
- **Buffer / Temp File Mode (`temp_file`)**: Optional fallback mode that downloads to local disk first, verifies, uploads to GCS, and cleans up.
- **Native GCP VM Authentication**: Uses Application Default Credentials (ADC) attached to the GCP VM's service account (no JSON keys needed on VM if configured).
- **SSH Key & Password Support**: Connects to SFTP using either password, SSH key file, or encrypted passphrase-protected keys.
- **Single File or Batch Directory Sync**: Supports syncing a single remote file or all files inside an SFTP directory.
- **Integrity Check**: Verifies that uploaded blob size on GCS matches the source SFTP file size.
- **Optional Cleanup**: Can delete the source file from SFTP after successful upload (`DELETE_AFTER_UPLOAD=true`).

---

## 🚀 Step 1: GCP VM & Bucket Prerequisites

### 1. Grant Bucket Access to the VM (Best Practice - No Key File Needed)
When you create a GCP Compute Engine VM, it has an attached Service Account (default: `<project-number>-compute@developer.gserviceaccount.com`).

1. Open **Google Cloud Console** -> **Cloud Storage** -> **Buckets**.
2. Click your bucket name -> **Permissions** tab -> **Grant Access**.
3. In **New principals**, enter your VM's Service Account email.
4. Assign the role **Storage Object Admin** (or **Storage Object Creator**).
5. Click **Save**.

*(Note: If you prefer using a downloaded Service Account JSON key, place it on the VM and set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json` in `.env`)*

---

## 💻 Step 2: Push to GitHub & Pull onto GCP VM

### From your local machine:
```bash
git init
git add .
git commit -m "Initial commit: SFTP to GCS sync pipeline"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPOSITORY>.git
git push -u origin main
```

### On your GCP VM:
SSH into your GCP VM (via Google Cloud Console or `gcloud compute ssh <vm-name>`):

```bash
# Clone the repository
git clone https://github.com/<YOUR_USERNAME>/<YOUR_REPOSITORY>.git
cd <YOUR_REPOSITORY>

# Run automated setup
chmod +x setup.sh
./setup.sh
```

---

## 🔧 Step 3: Configure Environment Variables

1. Edit the generated `.env` file:
   ```bash
   nano .env
   ```

2. Fill in your details:
   ```env
   # SFTP Server Details
   SFTP_HOST=sftp.yourpartner.com
   SFTP_PORT=22
   SFTP_USER=my_sftp_user
   SFTP_PASSWORD=my_secure_password
   # Or SFTP_KEY_PATH=/home/username/.ssh/sftp_key.pem

   # Path to the file or directory on SFTP
   SFTP_REMOTE_PATH=/exports/daily_data.csv

   # GCS Configuration
   GCS_BUCKET_NAME=my-gcp-bucket-name
   GCS_DESTINATION_PREFIX=incoming/

   # Transfer Options
   TRANSFER_MODE=stream
   DELETE_AFTER_UPLOAD=false
   ```
   Save and exit (`Ctrl + O`, then `Enter`, then `Ctrl + X`).

---

## 🏃 Step 4: Run the Transfer

Activate the virtual environment and run the script:

```bash
source venv/bin/activate
python main.py
```

### Command Line Overrides
You can also pass arguments to override `.env` values dynamically:

```bash
# Transfer a specific file
python main.py --remote-path /exports/file_2026.csv

# Transfer and store under a custom GCS subfolder
python main.py --remote-path /exports/file.csv --prefix archives/2026/

# Transfer and delete from SFTP after success
python main.py --remote-path /exports/file.csv --delete-remote

# Run with file logging
python main.py --log-file transfer.log
```

---

## ⏰ Step 5: Schedule Automation on GCP VM

### Option A: Using Crontab (Simplest)
To run the transfer daily at 2:00 AM:

```bash
crontab -e
```
Add the following line (replace paths with your VM's absolute paths):
```text
0 2 * * * cd /home/YOUR_USER/<YOUR_REPO> && ./venv/bin/python main.py >> /home/YOUR_USER/<YOUR_REPO>/cron.log 2>&1
```

### Option B: Using Systemd Service & Timer (Recommended for Production)
1. Update user and path in `systemd/sftp-to-gcs.service`:
   ```bash
   nano systemd/sftp-to-gcs.service
   ```
2. Copy systemd unit files:
   ```bash
   sudo cp systemd/sftp-to-gcs.service /etc/systemd/system/
   sudo cp systemd/sftp-to-gcs.timer /etc/systemd/system/
   ```
3. Enable and start the timer:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now sftp-to-gcs.timer
   ```
4. Check status and logs:
   ```bash
   systemctl list-timers --all
   journalctl -u sftp-to-gcs.service -f
   ```

---

## 🔍 Verification

Once executed:
1. Go to **Google Cloud Console** -> **Cloud Storage** -> **Buckets**.
2. Open your bucket and navigate to the prefix (e.g., `incoming/`).
3. You will see the transferred file with matching file size and timestamp.
