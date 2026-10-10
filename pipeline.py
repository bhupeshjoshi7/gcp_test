#!/usr/bin/env python3
"""
Master Pipeline Orchestrator: Argon -> GCS -> Cloud SQL -> Business Logic
Chains Step 1, Step 2, and Step 3 together with timing and error handling.
Designed for execution on business days via crontab or systemd timer.
"""

import argparse
import datetime
import logging
import sys
import time

from step1_sftp_to_gcs import run_step1
from step2_gcs_to_postgres import run_step2
from step3_business_logic import run_step3

logger = logging.getLogger("pipeline")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [Pipeline] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_pipeline(skip_step1=False, skip_step2=False, skip_step3=False, init_schema=False):
    """Runs the 3-step pipeline sequentially."""
    start_time = time.time()
    today_str = datetime.date.today().strftime("%Y-%m-%d (%A)")
    logger.info("==================================================================")
    logger.info("Starting Daily Data Pipeline for: %s", today_str)
    logger.info("==================================================================")

    steps_status = {}

    # -------------------------------------------------------------------------
    # STEP 1: Argon SFTP -> GCS
    # -------------------------------------------------------------------------
    if not skip_step1:
        logger.info("--> [1/3] EXECUTING: Step 1 (Argon SFTP -> GCS)...")
        step1_start = time.time()
        step1_ok = run_step1()
        step1_duration = time.time() - step1_start
        steps_status["Step 1 (SFTP -> GCS)"] = ("SUCCESS" if step1_ok else "FAILED", f"{step1_duration:.2f}s")
        if not step1_ok:
            logger.error("Pipeline aborted: Step 1 failed!")
            print_summary(steps_status, time.time() - start_time)
            return False
    else:
        logger.info("Skipping Step 1 as requested.")
        steps_status["Step 1 (SFTP -> GCS)"] = ("SKIPPED", "0.00s")

    # -------------------------------------------------------------------------
    # STEP 2: GCS -> Cloud SQL (PostgreSQL)
    # -------------------------------------------------------------------------
    if not skip_step2:
        logger.info("--> [2/3] EXECUTING: Step 2 (GCS -> Cloud SQL)...")
        step2_start = time.time()
        step2_ok = run_step2()
        step2_duration = time.time() - step2_start
        steps_status["Step 2 (GCS -> Cloud SQL)"] = ("SUCCESS" if step2_ok else "FAILED", f"{step2_duration:.2f}s")
        if not step2_ok:
            logger.error("Pipeline aborted: Step 2 failed!")
            print_summary(steps_status, time.time() - start_time)
            return False
    else:
        logger.info("Skipping Step 2 as requested.")
        steps_status["Step 2 (GCS -> Cloud SQL)"] = ("SKIPPED", "0.00s")

    # -------------------------------------------------------------------------
    # STEP 3: Business Logic & Analytics
    # -------------------------------------------------------------------------
    if not skip_step3:
        logger.info("--> [3/3] EXECUTING: Step 3 (Business Logic Transformations)...")
        step3_start = time.time()
        step3_ok = run_step3(init_schema=init_schema)
        step3_duration = time.time() - step3_start
        steps_status["Step 3 (Business Logic)"] = ("SUCCESS" if step3_ok else "FAILED", f"{step3_duration:.2f}s")
        if not step3_ok:
            logger.error("Pipeline aborted: Step 3 failed!")
            print_summary(steps_status, time.time() - start_time)
            return False
    else:
        logger.info("Skipping Step 3 as requested.")
        steps_status["Step 3 (Business Logic)"] = ("SKIPPED", "0.00s")

    total_duration = time.time() - start_time
    print_summary(steps_status, total_duration)
    return True


def print_summary(steps_status: dict, total_duration: float):
    logger.info("==================================================================")
    logger.info("                     PIPELINE EXECUTION SUMMARY                   ")
    logger.info("==================================================================")
    for step_name, (status, duration) in steps_status.items():
        logger.info("  * %-30s : %-10s (Time: %s)", step_name, status, duration)
    logger.info("------------------------------------------------------------------")
    logger.info("  Total Pipeline Elapsed Time: %.2f seconds", total_duration)
    logger.info("==================================================================")


def main():
    parser = argparse.ArgumentParser(description="Master Data Pipeline Orchestrator.")
    parser.add_argument("--only-step", type=int, choices=[1, 2, 3], help="Run only a single specific step")
    parser.add_argument("--skip-step1", action="store_true", help="Skip Step 1 (SFTP to GCS)")
    parser.add_argument("--skip-step2", action="store_true", help="Skip Step 2 (GCS to Cloud SQL)")
    parser.add_argument("--skip-step3", action="store_true", help="Skip Step 3 (Business Logic)")
    parser.add_argument("--init-schema", action="store_true", help="Run schema.sql to initialize tables before business logic")
    args = parser.parse_args()

    setup_logging()

    if args.only_step:
        skip1 = args.only_step != 1
        skip2 = args.only_step != 2
        skip3 = args.only_step != 3
    else:
        skip1 = args.skip_step1
        skip2 = args.skip_step2
        skip3 = args.skip_step3

    success = run_pipeline(skip_step1=skip1, skip_step2=skip2, skip_step3=skip3, init_schema=args.init_schema)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
