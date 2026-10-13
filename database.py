"""MySQL connection helper; credentials are read from the process environment."""

import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv


# Load this project's local .env without overriding variables already provided
# by the shell or deployment environment.
load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "hostel_management"),
        connection_timeout=5,
    )
