# End-to-End Enterprise Architecture & Setup Guide
## Argon SFTP ➔ Google Cloud Storage (GCS) ➔ Cloud SQL (PostgreSQL) ➔ Business Logic

This document provides complete, reproducible, step-by-step documentation for deploying, configuring, and running the automated business-day data pipeline on Google Cloud Platform.

---

## 1. System Architecture & Data Flow

```text
       ┌────────────────────────┐
       │   Argon SFTP Server    │  (External Partner / Cluster)
       └───────────┬────────────┘
                   │
                   │ [Step 1: SFTP Streaming]
                   ▼
       ┌────────────────────────┐
       │ Google Cloud Storage   │  Raw Data Lake Archive
       │ gs://sdsd-dump/raw/    │  Timestamped: YYYY-MM-DD/file.csv
       └───────────┬────────────┘
                   │
                   │ [Step 2: GCS Streaming Bulk COPY]
                   ▼
       ┌────────────────────────┐
       │ GCP Cloud SQL Postgres │  Staging Table
       │ (staging_argon_data)   │  High-speed native ingest
       └───────────┬────────────┘
                   │
                   │ [Step 3: Business Logic Transformations]
                   ▼
       ┌────────────────────────┐
       │ Production Analytics   │  • argon_data (Upserted / Merged)
       │ & Reporting Tables     │  • daily_category_summary (Aggregations)
       └────────────────────────┘
```

---

## 2. Project File Structure

```text
gcp_test/
├── .env.example              # Documented configuration template
├── .gitignore                # Protects secrets, venvs, and logs from Git
├── requirements.txt          # Dependencies (google-cloud-storage, paramiko, psycopg2-binary, python-dotenv)
├── config.py                 # Centralized configuration loader and validator
│
├── step1_sftp_to_gcs.py      # Step 1: Pull from Argon SFTP and stream to GCS bucket
├── step2_gcs_to_postgres.py  # Step 2: Stream from GCS directly into Cloud SQL staging table via COPY
├── step3_business_logic.py   # Step 3: Run SQL transformations and upsert into production tables
├── pipeline.py               # Master Orchestrator: Chains Steps 1 -> 2 -> 3 with failure alerts
│
├── sql/
│   ├── schema.sql            # Table DDL (staging_argon_data and argon_data)
│   └── business_logic.sql    # Business queries (upsert, conflict resolution, summaries)
│
├── systemd/
│   ├── pipeline.service      # Systemd service unit for the pipeline
│   └── pipeline.timer        # Systemd timer unit scheduled for Business Days (Mon-Fri)
│
└── ARCHITECTURE_AND_SETUP.md # This master deployment guide
```

---

## 3. Step-by-Step GCP Infrastructure Setup

### 3.1. Google Cloud Storage (GCS) Bucket
1. Go to **Google Cloud Console** -> **Cloud Storage** -> **Buckets**.
2. Click **Create** -> Bucket Name: `sdsd-dump` (or your chosen name) -> Choose Region (e.g. `us-central1` or your VM's region) -> Standard Storage -> Uniform access control.
3. Grant permissions to your VM Service Account:
   - Go to **Permissions** tab -> **Grant Access**.
   - Principal: `9394767867-compute@developer.gserviceaccount.com`
   - Role: **Storage Object Admin** (`roles/storage.objectAdmin`).

---

### 3.2. Google Cloud SQL (PostgreSQL) Instance (Cost-Optimized)

To minimize cost, we select the lowest tier instance (`db-f1-micro` or `db-custom-1-3840`):

#### Creating via Google Cloud Console:
1. Go to **SQL** -> Click **Create Instance**.
2. Choose **PostgreSQL**.
3. **Instance ID**: `argon-postgres-db`
4. **Password**: Set a strong password for user `postgres`.
5. **Database Version**: PostgreSQL 16 (or 15).
6. Under **Configuration Options** -> **Machine type**:
   - Select **Shared core** -> `db-f1-micro` (1 vCPU, 0.614 GB RAM) for lowest cost (~$10/month).
7. Under **Storage**:
   - Set 10 GB SSD, disable automatic storage increase if testing.
8. Under **Connections**:
   - **Recommended (Zero Public Exposure)**: Enable **Private IP** (associates with default VPC network).
   - If using Private IP, your GCP VM connects directly via the internal IP (e.g., `10.x.x.x`).
   - If using Public IP, check **Public IP** and either use the **Cloud SQL Auth Proxy** or add your VM's public IP to **Authorized networks**.
9. Click **Create Instance**.

#### Creating via gcloud CLI (Alternative):
```bash
gcloud sql instances create argon-postgres-db \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region=us-central1 \
    --root-password="YOUR_STRONG_PASSWORD" \
    --storage-size=10GB
```

#### Grant Cloud SQL Client Role to the VM Service Account:
1. Go to **IAM & Admin** -> **IAM**.
2. Find `9394767867-compute@developer.gserviceaccount.com`.
3. Click the pencil icon (Edit) -> **+ Add Another Role**.
4. Select: **Cloud SQL Client** (`roles/cloudsql.client`).
5. Click **Save**.

---

### 3.3. Connecting VM to Cloud SQL

#### Option A: Direct Private IP (Recommended when Cloud SQL has Private IP enabled)
Simply find the Private IP in the Cloud SQL Overview tab (e.g., `10.128.0.3`) and set `DB_HOST=10.128.0.3` in `.env`.

#### Option B: Cloud SQL Auth Proxy (Recommended for Public IP or Encrypted Local Socket)
On your GCP VM:
```bash
# 1. Download Cloud SQL Auth Proxy
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.0/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy

# 2. Start proxy in background (replace PROJECT_ID, REGION, INSTANCE_ID)
# The proxy listens on 127.0.0.1:5432
./cloud-sql-proxy <PROJECT_ID>:<REGION>:argon-postgres-db --port 5432 &
```
Then in `.env`, set `DB_HOST=127.0.0.1`.

---

## 4. Environment Configuration (`.env`)

On your GCP VM, create `.env` inside `~/gcp_test/.env`:

```env
# =====================================================================
# SFTP Configuration (Argon Source)
# =====================================================================
SFTP_HOST=argon.yourdomain.com
SFTP_PORT=22
SFTP_USER=bhupeshjoshi2k4
SFTP_PASSWORD=
SFTP_KEY_PATH=/home/bhupeshjoshi2k4/.ssh/id_ed25519
SFTP_KEY_PASSPHRASE=

# Remote File to Fetch
SFTP_REMOTE_PATH=/home/bhupeshjoshi2k4/sample_test.csv

# =====================================================================
# Google Cloud Storage (GCS)
# =====================================================================
GCS_BUCKET_NAME=sdsd-dump
GCS_DESTINATION_PREFIX=raw/
TRANSFER_MODE=stream
DELETE_AFTER_UPLOAD=false

# =====================================================================
# Google Cloud SQL (PostgreSQL)
# =====================================================================
# If using Cloud SQL Auth Proxy: 127.0.0.1
# If using Cloud SQL Private IP: 10.x.x.x
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your_cloud_sql_password
DB_SSLMODE=prefer

# Target tables in Cloud SQL
DB_STAGING_TABLE=staging_argon_data
DB_PROD_TABLE=argon_data
```

---

## 5. Setting Up the Virtual Environment on the VM

Run the following commands on your GCP VM:

```bash
cd ~/gcp_test

# 1. Pull the latest repository updates
git pull

# 2. Activate virtual environment
source venv/bin/activate

# 3. Install/Update dependencies (includes psycopg2-binary)
pip install -r requirements.txt

# 4. Initialize Database Tables in Cloud SQL
python step3_business_logic.py --init-schema
```

---

## 6. Running the Pipeline

### Testing Steps Individually:

#### Test Step 1: Pull from Argon SFTP -> GCS Bucket
```bash
python step1_sftp_to_gcs.py
```
*Output: Streams file from SFTP and uploads to `gs://sdsd-dump/raw/YYYY-MM-DD/file.csv`.*

#### Test Step 2: GCS Bucket -> Cloud SQL Staging Table
```bash
python step2_gcs_to_postgres.py
```
*Output: Streams the latest CSV from GCS and bulk `COPY`s it into `staging_argon_data`.*

#### Test Step 3: Run Business Logic & Upsert
```bash
python step3_business_logic.py
```
*Output: Merges staging rows into `argon_data` and computes daily summaries.*

---

### Running the Full Master Pipeline:
```bash
python pipeline.py
```

Sample output:
```text
2026-10-10 04:00:01 [INFO] [Pipeline] ==================================================================
2026-10-10 04:00:01 [INFO] [Pipeline] Starting Daily Data Pipeline for: 2026-10-12 (Monday)
2026-10-10 04:00:01 [INFO] [Pipeline] ==================================================================
2026-10-10 04:00:01 [INFO] [Pipeline] --> [1/3] EXECUTING: Step 1 (Argon SFTP -> GCS)...
2026-10-10 04:00:03 [INFO] [Pipeline] --> [2/3] EXECUTING: Step 2 (GCS -> Cloud SQL)...
2026-10-10 04:00:04 [INFO] [Pipeline] --> [3/3] EXECUTING: Step 3 (Business Logic)...
2026-10-10 04:00:05 [INFO] [Pipeline] ==================================================================
2026-10-10 04:00:05 [INFO] [Pipeline]                      PIPELINE EXECUTION SUMMARY                   
2026-10-10 04:00:05 [INFO] [Pipeline] ==================================================================
2026-10-10 04:00:05 [INFO] [Pipeline]   * Step 1 (SFTP -> GCS)           : SUCCESS    (Time: 2.14s)
2026-10-10 04:00:05 [INFO] [Pipeline]   * Step 2 (GCS -> Cloud SQL)      : SUCCESS    (Time: 1.05s)
2026-10-10 04:00:05 [INFO] [Pipeline]   * Step 3 (Business Logic)        : SUCCESS    (Time: 0.82s)
2026-10-10 04:00:05 [INFO] [Pipeline] ------------------------------------------------------------------
2026-10-10 04:00:05 [INFO] [Pipeline]   Total Pipeline Elapsed Time: 4.01 seconds
2026-10-10 04:00:05 [INFO] [Pipeline] ==================================================================
```

---

## 7. Automating on Business Days (Monday – Friday)

### Option A: Using Crontab (Simplest)
Open crontab:
```bash
crontab -e
```
Add this entry to run at **04:00 AM UTC every Monday through Friday** (`1-5`):
```text
0 4 * * 1-5 cd /home/bhupeshjoshi2k4/gcp_test && ./venv/bin/python pipeline.py >> /home/bhupeshjoshi2k4/gcp_test/pipeline.log 2>&1
```

---

### Option B: Using Systemd Service & Timer (Recommended for Production)

1. Verify user paths inside `systemd/pipeline.service`:
   ```ini
   User=bhupeshjoshi2k4
   WorkingDirectory=/home/bhupeshjoshi2k4/gcp_test
   ExecStart=/home/bhupeshjoshi2k4/gcp_test/venv/bin/python pipeline.py
   ```

2. Copy the unit files:
   ```bash
   sudo cp systemd/pipeline.service /etc/systemd/system/
   sudo cp systemd/pipeline.timer /etc/systemd/system/
   ```

3. Enable and activate the business-day timer:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now pipeline.timer
   ```

4. Verify timer schedule:
   ```bash
   systemctl list-timers pipeline.timer
   ```
   *(It will show `Mon..Fri` and display the exact next trigger time).*

5. View real-time logs:
   ```bash
   journalctl -u pipeline.service -f
   ```

---

## 8. Summary of All Shell Commands Cheat-Sheet

```bash
# ----------------------------------------------------
# 1. PULL CODE & CONFIGURE
# ----------------------------------------------------
cd ~/gcp_test
git pull
source venv/bin/activate
pip install -r requirements.txt

# ----------------------------------------------------
# 2. INITIALIZE DB TABLES IN CLOUD SQL
# ----------------------------------------------------
python step3_business_logic.py --init-schema

# ----------------------------------------------------
# 3. TEST RUNS
# ----------------------------------------------------
python step1_sftp_to_gcs.py        # Run Step 1 only
python step2_gcs_to_postgres.py    # Run Step 2 only
python step3_business_logic.py     # Run Step 3 only
python pipeline.py                 # Run entire 3-step pipeline

# ----------------------------------------------------
# 4. SETUP AUTOMATION FOR BUSINESS DAYS (MON-FRI)
# ----------------------------------------------------
crontab -e
# Add: 0 4 * * 1-5 cd /home/bhupeshjoshi2k4/gcp_test && ./venv/bin/python pipeline.py >> /home/bhupeshjoshi2k4/gcp_test/pipeline.log 2>&1
```
