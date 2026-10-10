#!/usr/bin/env python3
"""
Step 3: Business Logic Execution
Executes business logic transformations, merging staging data into production tables,
and computing analytics/reports in Cloud SQL PostgreSQL.
"""

import argparse
import logging
import os
import sys
import psycopg2

from config import load_config

logger = logging.getLogger("step3_business_logic")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [Step 3: Business Logic] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_step3(sql_file_path: str = None, init_schema: bool = False) -> bool:
    """Executes Step 3: Run SQL transformations and business rules."""
    config = load_config()

    if not config.db_host or not config.db_user or not config.db_name:
        logger.error("Missing database configuration (DB_HOST, DB_USER, DB_NAME in .env).")
        return False

    base_dir = os.path.dirname(os.path.abspath(__file__))
    schema_file = os.path.join(base_dir, "sql", "schema.sql")
    logic_file = sql_file_path or os.path.join(base_dir, "sql", "business_logic.sql")

    if not os.path.exists(logic_file):
        logger.error("Business logic SQL file not found: %s", logic_file)
        return False

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
        cursor = conn.cursor()

        # Step A: Initialize schema if requested or tables missing
        if init_schema and os.path.exists(schema_file):
            logger.info("Ensuring database schema exists from %s...", schema_file)
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            cursor.execute(schema_sql)
            conn.commit()
            logger.info("Database schema initialized.")

        # Step B: Execute business logic SQL script
        logger.info("Executing business logic SQL from %s...", logic_file)
        with open(logic_file, "r", encoding="utf-8") as f:
            business_sql = f.read()

        cursor.execute(business_sql)
        conn.commit()

        # Step C: Check row counts in production table
        cursor.execute(f"SELECT COUNT(*) FROM {config.db_prod_table};")
        total_prod_rows = cursor.fetchone()[0]
        logger.info("Step 3 completed successfully! Production table '%s' now has %d total records.",
                    config.db_prod_table, total_prod_rows)

        cursor.close()
        return True

    except Exception as e:
        logger.error("Step 3 failed during business logic execution: %s", e, exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")


def main():
    parser = argparse.ArgumentParser(description="Step 3: Execute Business Logic SQL in Cloud SQL.")
    parser.add_argument("--sql-file", type=str, help="Custom SQL file to execute (defaults to sql/business_logic.sql)")
    parser.add_argument("--init-schema", action="store_true", help="Run sql/schema.sql to create tables first")
    args = parser.parse_args()

    setup_logging()
    success = run_step3(sql_file_path=args.sql_file, init_schema=args.init_schema)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
