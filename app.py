"""Local Flask application for analysing synthetic communication-log patterns."""
from __future__ import annotations

import io
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from models.detector import REQUIRED_COLUMNS, analyze_logs

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database.db"
SAMPLE_FILE = BASE_DIR / "data" / "sample_logs.csv"
REPORTS_DIR = BASE_DIR / "reports"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "local-demo-key-change-before-sharing")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
PORT = int(os.environ.get("PORT", "5000"))


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    """Create the one-table SQLite store and load demo records on first run."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS communication_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                receiver_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                message_type TEXT NOT NULL,
                response_status TEXT NOT NULL
            )
        """)
        row_count = connection.execute("SELECT COUNT(*) FROM communication_logs").fetchone()[0]
        if row_count == 0 and SAMPLE_FILE.exists():
            sample = pd.read_csv(SAMPLE_FILE)
            if not sample.empty:
                _replace_logs(connection, sample)


def _replace_logs(connection: sqlite3.Connection, frame: pd.DataFrame) -> None:
    columns = ["timestamp", "sender_id", "receiver_id", "platform", "message_type", "response_status"]
    rows = [tuple(str(value) for value in row) for row in frame[columns].itertuples(index=False, name=None)]
    connection.execute("DELETE FROM communication_logs")
    connection.executemany(
        """INSERT INTO communication_logs
           (timestamp, sender_id, receiver_id, platform, message_type, response_status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows,
    )


def load_logs() -> pd.DataFrame:
    with get_connection() as connection:
        return pd.read_sql_query(
            "SELECT timestamp, sender_id, receiver_id, platform, message_type, response_status "
            "FROM communication_logs ORDER BY timestamp",
            connection,
        )


def validate_csv(file_bytes: bytes) -> pd.DataFrame:
    """Parse and validate the upload before it can replace the active dataset."""
    if not file_bytes:
        raise ValueError("The uploaded file is empty.")
    try:
        frame = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as error:
        raise ValueError("Could not read this CSV. Check its encoding, header row, and delimiters.") from error
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    if len(frame) > 100_000:
        raise ValueError("The CSV contains more than 100,000 rows; split it into smaller files.")

    frame = frame[list(REQUIRED_COLUMNS)].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"].str.strip(), errors="coerce", utc=True)
    if frame["timestamp"].isna().any():
        raise ValueError("Every row needs a valid timestamp, such as 2025-03-14 09:30:00.")
    for column in ("sender_id", "receiver_id"):
        frame[column] = frame[column].astype(str).str.strip()
        if frame[column].eq("").any():
            raise ValueError(f"Every row needs a non-empty {column} value.")
    for column in ("platform", "message_type", "response_status"):
        frame[column] = frame[column].astype(str).str.strip().replace("", "unspecified")
    frame["timestamp"] = frame["timestamp"].map(lambda value: value.isoformat())
    return frame


def current_analysis() -> dict:
    return analyze_logs(load_logs())


@app.route("/")
def dashboard():
    analysis = current_analysis()
    return render_template("dashboard.html", analysis=analysis)


@app.route("/analysis")
def analysis_page():
    return render_template("analysis.html", analysis=current_analysis())


@app.route("/upload", methods=["POST"])
def upload():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        flash("Choose a CSV file before uploading.", "error")
        return redirect(url_for("dashboard"))
    if Path(secure_filename(uploaded.filename)).suffix.lower() != ".csv":
        flash("Only CSV files are accepted.", "error")
        return redirect(url_for("dashboard"))
    raw = uploaded.stream.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        flash("The file is larger than the 5 MB upload limit.", "error")
        return redirect(url_for("dashboard"))
    try:
        frame = validate_csv(raw)
        with get_connection() as connection:
            _replace_logs(connection, frame)
    except (ValueError, sqlite3.Error) as error:
        flash(str(error), "error")
        return redirect(url_for("dashboard"))
    flash(f"Loaded {len(frame):,} validated communication record(s).", "success")
    return redirect(url_for("dashboard"))


def build_report_text(analysis: dict) -> str:
    lines = [
        "CYBERSTALKING BEHAVIOUR PATTERN DETECTOR - SUMMARY REPORT",
        "Generated: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "",
        "SCOPE AND SAFETY",
        "This report describes observable patterns in supplied logs. It is not a legal or psychological diagnosis and does not identify intent or a person.",
        "",
        "ANALYSIS PERIOD",
        f"{analysis['period_start'] or 'No data'} to {analysis['period_end'] or 'No data'} ({analysis['period_days']} day(s))",
        "",
        "COMMUNICATION STATISTICS",
        f"Messages: {analysis['total_messages']}",
        f"Unique sender/receiver accounts: {analysis['unique_accounts']}",
        f"Average messages per day: {analysis['average_per_day']}",
        f"Messages in repeated-contact pairs: {analysis['repeated_contact_count']}",
        "",
        "OVERALL PATTERN SUMMARY",
        analysis["summary"],
        "",
        "RISK INDICATORS",
    ]
    if analysis["indicators"]:
        lines.extend(f"- {item['name']}: {item['count']} sender profile(s)" for item in analysis["indicators"])
    else:
        lines.append("No rule-based indicators were counted.")
    lines.extend(["", "SENDER PROFILES"])
    for sender in analysis["sender_summaries"]:
        lines.append(
            f"- {sender['sender_id']}: {sender['risk_level']}; "
            f"{sender['message_count']} messages; indicators: {', '.join(sender['indicators'])}"
        )
    lines.extend(["", "MACHINE-LEARNING NOTE", analysis["ml_note"], ""])
    return "\n".join(lines)


@app.route("/report")
def report():
    analysis = current_analysis()
    report_text = build_report_text(analysis)
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / "latest_summary_report.txt"
    report_path.write_text(report_text, encoding="utf-8")
    return render_template("report.html", analysis=analysis, report_text=report_text)


@app.route("/report/download")
def download_report():
    report_path = REPORTS_DIR / "latest_summary_report.txt"
    if not report_path.exists():
        build_report_text(current_analysis())
        REPORTS_DIR.mkdir(exist_ok=True)
        report_path.write_text(build_report_text(current_analysis()), encoding="utf-8")
    return send_file(report_path, as_attachment=True, download_name="communication_pattern_report.txt", mimetype="text/plain")


@app.errorhandler(413)
def upload_too_large(_error):
    flash("The file is larger than the 5 MB upload limit.", "error")
    return redirect(url_for("dashboard"))


initialize_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
