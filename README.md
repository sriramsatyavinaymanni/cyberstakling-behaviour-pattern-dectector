# Cyberstalking Behaviour Pattern Detector

A beginner-friendly, local Flask project for exploring patterns in **synthetic/demo communication logs**. It highlights observable patterns such as repeated contact, frequency changes, unanswered attempts, and cross-platform contact. It does not identify people or determine intent.

> **Safety boundary:** This is an educational pattern-review tool, not a legal or psychological diagnosis. Do not upload credentials, private messages, or sensitive personal information. Use synthetic or appropriately authorized and minimized data. The app does not scrape social websites or attempt to locate anyone.

## Quick Start on Windows

Python 3.11 or newer is recommended. Open this `cyberstalking_detector` folder in VS Code, then open **Terminal → New Terminal** and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. Stop Flask with `Ctrl+C`. If PowerShell blocks activation, run the commands directly through the virtual-environment interpreter:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

The Flask development server is for local demonstration only. Do not expose it to the public internet. The project uses Chart.js and web fonts from public CDNs, so those visual assets require internet access; the Flask server and analysis run locally.

## Project Layout

```text
cyberstalking_detector/
├── app.py                       Flask routes, CSV validation, SQLite, report generation
├── requirements.txt             Python packages
├── README.md                    Setup and project documentation
├── database.db                  Created and seeded on first run
├── data/sample_logs.csv         Synthetic demo records
├── models/detector.py           Transparent rules and Isolation Forest signal
├── models/__init__.py            Analysis package marker
├── templates/index.html         Shared page shell and navigation
├── templates/dashboard.html     Dashboard, upload, charts, filters, log table
├── templates/analysis.html      Rule definitions and sender profiles
├── templates/report.html        Printable/downloadable report with charts
├── static/css/style.css         Responsive dashboard styling
├── static/js/dashboard.js       Chart.js charts and log filters
├── tests/test_app.py            Focused automated checks
└── reports/                     Generated summaries are written here
```

SQLite creates `database.db` and seeds it from the sample file when the app first starts. A successful upload replaces the active rows; a rejected upload leaves the database unchanged. Reports are saved to `reports/latest_summary_report.txt`.

## CSV Upload Format

Upload a UTF-8 CSV no larger than 5 MB and 100,000 rows. Headers are case-insensitive; all six are required:

| Column | Description | Example |
| --- | --- | --- |
| `timestamp` | Date/time of a record | `2025-05-01 09:15:00` |
| `sender_id` | Synthetic or authorized account label | `demo_sender_01` |
| `receiver_id` | Synthetic or authorized recipient label | `demo_receiver_A` |
| `platform` | Channel label | `Forum` |
| `message_type` | Coarse event type | `direct message` |
| `response_status` | Status included with the record | `unanswered`, `replied`, `unknown` |

Timestamps must be parseable; sender and receiver cannot be blank. Missing optional text values become `unspecified`. A CSV with just the six required headers and no data rows is valid and clears the active dataset. Invalid files receive a visible error. Recognized unanswered values are `no`, `none`, `unanswered`, `no_response`, `no response`, and `not replied`.

## Project Documentation

### 1. Abstract

This local web application summarizes communication activity from synthetic or authorized CSV records. It combines explainable frequency and interaction rules with optional unsupervised outlier detection, then presents the results as counts, charts, filters, and a report. Its output is limited to behavioural indicators and is not a conclusion about identity, intent, criminality, or diagnosis.

### 2. Problem Statement

Large communication logs can make repeated contact, increasing activity, unanswered attempts, or cross-channel patterns difficult to review consistently. A simple, explainable interface can help a user find these observable patterns in a supplied dataset while preserving human interpretation and privacy boundaries.

### 3. Objectives

- Load synthetic/demo communication records from CSV.
- Validate data before replacing the current dataset.
- Summarize messages, accounts, period, and repeated pairs.
- Apply visible rules for frequency, changes over time, unanswered status, and channel diversity.
- Optionally flag statistical outliers for human review.
- Provide charts, filters, a table, and a printable/downloadable report.
- Avoid accusation, identity discovery, scraping, and sensitive-data collection.

### 4. Existing System

Manual review often means scrolling through messages or spreadsheets. It can be slow, inconsistent, and difficult to summarize across time or multiple channels. Opaque anomaly scores are also hard to interpret without visible reasoning.

### 5. Proposed System

The app validates a fixed set of CSV fields, stores them locally in SQLite, and uses Pandas/NumPy to aggregate activity. Rule checks produce explicit indicators, including when a sender's records span multiple receiver account labels; an optional Scikit-learn Isolation Forest highlights profiles whose feature combinations differ from peers. Flask serves the pages, JavaScript manages filters, and Chart.js draws the visualizations. The ML output does not determine the rule-based label.

### 6. System Architecture

```text
Synthetic sample or CSV upload
          ↓
Flask validation: columns, size, values, timestamps
          ↓
SQLite communication_logs
          ↓
Pandas/NumPy aggregation ──→ transparent indicator rules
          │                                  │
          └── optional Scikit-learn Isolation Forest
                                             ↓
          Flask templates + JavaScript + Chart.js + report
```

All data analysis occurs in the local Flask process. Chart.js and fonts use public CDNs.

### 7. Modules

- **Dashboard:** metrics, overall summary, five visualizations, filters, log table, and upload.
- **Upload/validation:** validates before transactionally replacing the active dataset.
- **Analysis:** aggregates dates, sender profiles, repeated pairs, response statuses, receiver-account diversity, platforms, and frequency changes.
- **Rule detector:** produces understandable indicators and cautious labels.
- **Anomaly detector:** optionally marks outliers when at least five senders are present.
- **Report generator:** saves a UTF-8 text summary; the report page includes charts and browser printing.
- **SQLite storage:** keeps the active dataset locally between restarts.

### 8. Technologies Used

| Technology | Purpose |
| --- | --- |
| Python | Application and analysis logic |
| Flask | Local routes and web server |
| HTML5 / CSS3 | Accessible pages and responsive layout |
| JavaScript | Filters and chart setup |
| SQLite | Local persistence |
| Pandas / NumPy | CSV and numeric analysis |
| Scikit-learn | Optional Isolation Forest |
| Chart.js | Interactive visualizations |

### 9. Database Design

The `communication_logs` table contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | Internal row ID |
| `timestamp` | TEXT NOT NULL | ISO-formatted UTC timestamp |
| `sender_id` | TEXT NOT NULL | Sender label |
| `receiver_id` | TEXT NOT NULL | Receiver label |
| `platform` | TEXT NOT NULL | Channel label |
| `message_type` | TEXT NOT NULL | Coarse event type |
| `response_status` | TEXT NOT NULL | Supplied status label |

Message contents, credentials, names, and locations are not part of the schema.

### 10. Algorithm Explanation

1. Read CSV values as text, normalize header names, and verify all required columns.
2. Parse timestamps to UTC; reject invalid timestamps or blank account IDs.
3. Replace current rows in one SQLite transaction only after validation succeeds.
4. Count messages by day, sender, platform, and sender/receiver pair.
5. Mark a pair repeated when it has at least three messages in the loaded dataset.
6. Compare average daily volume in the later half of observed days with the earlier half. An increase of 50% or more with at least four messages adds an increasing-frequency indicator.
7. Add cross-platform, multiple-receiver-account, and unanswered-status indicators using the thresholds displayed on Pattern analysis.
8. Assign cautious profile labels. These describe the records, not intent.

Average messages per day includes zero-message days between the first and last record. Frequency tiers use the sender's average across the same inclusive period.

### 11. Machine-Learning Explanation

Isolation Forest is unsupervised: it does not require examples labelled harmful or harmless. It repeatedly splits feature values; unusual combinations tend to be isolated with fewer splits. This project uses messages per day, repeated-contact count, unanswered-rate proxy, platform count, frequency change, and distinct receiver-account count. It runs only with five or more sender profiles and shows outliers for human review. An outlier is not necessarily harmful or meaningful.

The CSV has no response timestamp, so actual response delay cannot be calculated. The model uses the proportion of records marked unanswered as a response-related proxy; it does not represent a duration.

### 12. Screens/Pages

- **Dashboard (`/`):** summary cards, charts, upload, and sender/receiver/date/platform/indicator filters.
- **Pattern analysis (`/analysis`):** thresholds, profile-level indicators, and ML explanation/caveat.
- **Report (`/report`):** period, statistics, indicators, charts, observations, print, and text download.

### 13. Testing Procedure

With the environment active, run:

```powershell
python -m unittest discover -s tests -v
```

The suite checks empty data, demo analysis and ML availability, page responses, missing-column and timestamp rejection, preservation of records after a rejected upload, and safe rendering after a header-only CSV.

### 14. Sample Test Cases

| Case | Action | Expected result |
| --- | --- | --- |
| First run | Start with no database | SQLite is created and seeded |
| Valid upload | Provide required columns and valid timestamps | Data replaces current rows |
| Missing column | Omit `receiver_id` | Reject upload; keep existing rows |
| Invalid timestamp | Use `not-a-date` | Reject upload with a timestamp message |
| Empty file | Upload zero bytes | Reject with a readable message |
| Header-only CSV | Provide required headers and no rows | Empty dataset; pages remain available |
| Repeated pair | Add 3+ same-pair rows | Repeated-contact indicator appears |
| Cross-platform pair | Put same pair on 2 platforms | Cross-platform indicator appears |
| Small ML dataset | Include fewer than 5 senders | Rules work; ML signal unavailable |
| Filter | Select a sender/date/platform | Non-matching records are hidden |
| Report | Select Generate report | Report page and text download are available |

### 15. Advantages

- Local storage and processing.
- Synthetic sample data makes it immediately demonstrable.
- Visible thresholds explain every rule-based indicator.
- Malformed uploads do not replace valid active data.
- Combines charts, searchable records, and an exportable summary.
- Keeps anomaly output separate from rule-based labels.

### 16. Limitations

- Educational only; not a validated safety, forensic, clinical, or legal product.
- Incomplete or synthetic logs may not represent real communication.
- Repetition counts cover the whole dataset and do not distinguish burst timing.
- The half-period trend rule can be sensitive to short or sparse datasets.
- No response timestamps are supplied; unanswered status is only a proxy.
- Small profile samples can make ML outliers unstable or benign.
- CDN-based charts and fonts need internet access.
- Flask's built-in development server is not for public exposure.

### 17. Future Enhancements

- Optional time-windowed repetition rules and configurable thresholds.
- Response timestamps with an explicit delay calculation.
- CSV export and offline report chart assets.
- Confirmed local database-clear control.
- Broader accessibility, browser, and data validation tests.
- Privacy-reviewed evaluation before any real-world use.

### 18. Conclusion

The project demonstrates a privacy-conscious way to organize synthetic communication records and surface reviewable patterns. Rules are visible, data fields are narrow, and results are deliberately non-accusatory. Human context remains essential.

### 19. Demonstration Guide

1. Start Flask and show the `demo_` sample IDs on the dashboard.
2. Explain total messages, date range, daily average, and repeated-pair count.
3. Use a sender/platform/date filter and inspect a record.
4. Open Pattern analysis and explain a rule and the unanswered-status proxy.
5. Upload `data/sample_logs.csv`, then try a malformed CSV to show rejection without data loss.
6. Generate, print, or download the report and explain its caution notice.
7. Note that Isolation Forest requires at least five sender profiles.

### 20. Possible Viva Questions and Answers

1. **What does the project do?** It summarizes observable communication patterns in a supplied dataset.
2. **Why use rules?** They are visible, testable, and easy to explain.
3. **Does it identify a cyberstalker?** No. It cannot determine identity or intent.
4. **Why SQLite?** It is a lightweight local database that needs no separate server.
5. **What is repeated contact?** Three or more messages for one sender/receiver pair in the loaded dataset.
6. **How does Isolation Forest work?** It uses random splits; unusual feature combinations tend to be isolated sooner.
7. **Why is the ML model optional?** A comparative outlier signal is not useful with very few sender profiles.
8. **Can response delay be measured?** No, the CSV has no response timestamps; unanswered proportion is only a proxy.
9. **How are invalid uploads handled?** They are rejected before the active SQLite rows are replaced.
10. **What are the main limitations?** Data quality, simplistic thresholds, no response timing, and no validated real-world performance.
11. **Why synthetic data?** It allows a useful demo without exposing private communications or identifying real people.
12. **What would you improve?** Add time-windowed rules, response timestamps, offline charts, and further privacy-reviewed testing.
