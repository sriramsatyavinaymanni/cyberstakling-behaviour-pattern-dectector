"""Transparent behavioural indicators for synthetic communication logs.

The rules describe patterns in the supplied data. They do not identify or diagnose a person.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {
    "timestamp",
    "sender_id",
    "receiver_id",
    "platform",
    "message_type",
    "response_status",
}


def _frequency_change(daily_counts: pd.Series) -> float:
    """Compare the later half of observed days with the earlier half."""
    if len(daily_counts) < 2:
        return 0.0
    split_at = max(1, len(daily_counts) // 2)
    earlier = float(daily_counts.iloc[:split_at].mean())
    later = float(daily_counts.iloc[split_at:].mean())
    if later <= earlier:
        return 0.0
    return round((later - earlier) / max(earlier, 1.0), 3)


def analyze_logs(logs: pd.DataFrame) -> dict[str, Any]:
    """Analyze a validated dataframe and return JSON-friendly dashboard data."""
    if logs.empty:
        return {
            "total_messages": 0,
            "unique_accounts": 0,
            "average_per_day": 0,
            "repeated_contact_count": 0,
            "period_start": None,
            "period_end": None,
            "period_days": 0,
            "summary": "No communication records are available to analyze.",
            "indicators": [],
            "risk_distribution": [],
            "daily_counts": [],
            "sender_counts": [],
            "platform_counts": [],
            "sender_summaries": [],
            "logs": [],
            "ml_available": False,
            "ml_note": "Machine-learning analysis needs at least five distinct senders.",
        }

    data = logs.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce", utc=True)
    data = data.dropna(subset=["timestamp", "sender_id", "receiver_id"])
    if data.empty:
        return analyze_logs(pd.DataFrame())

    data["sender_id"] = data["sender_id"].astype(str)
    data["receiver_id"] = data["receiver_id"].astype(str)
    data["platform"] = data["platform"].fillna("unspecified").astype(str)
    data["message_type"] = data["message_type"].fillna("unspecified").astype(str)
    data["response_status"] = data["response_status"].fillna("unknown").astype(str)
    data = data.sort_values("timestamp")

    first_day = data["timestamp"].min().floor("D")
    last_day = data["timestamp"].max().floor("D")
    period_days = max(1, int((last_day - first_day).days) + 1)
    daily = data.assign(day=data["timestamp"].dt.strftime("%Y-%m-%d")).groupby("day").size()
    all_days = pd.date_range(first_day, last_day, freq="D", tz="UTC").strftime("%Y-%m-%d")
    daily = daily.reindex(all_days, fill_value=0)

    pair_counts = data.groupby(["sender_id", "receiver_id"]).size()
    repeated_pairs = set(pair_counts[pair_counts >= 3].index.tolist())
    data["repeated_contact"] = [
        (sender, receiver) in repeated_pairs
        for sender, receiver in zip(data["sender_id"], data["receiver_id"])
    ]

    no_response_values = {"no", "none", "unanswered", "no_response", "no response", "not replied"}
    data["after_non_response"] = data["response_status"].str.strip().str.lower().isin(no_response_values)
    pair_platforms = data.groupby(["sender_id", "receiver_id"])["platform"].nunique()
    cross_platform_pairs = set(pair_platforms[pair_platforms >= 2].index.tolist())
    data["cross_platform"] = [
        (sender, receiver) in cross_platform_pairs
        for sender, receiver in zip(data["sender_id"], data["receiver_id"])
    ]

    sender_summaries: list[dict[str, Any]] = []
    features: list[list[float]] = []
    for sender, group in data.groupby("sender_id"):
        sender_daily = group.groupby(group["timestamp"].dt.floor("D")).size().reindex(
            pd.date_range(first_day, last_day, freq="D", tz="UTC"), fill_value=0
        )
        sender_pairs = group.groupby("receiver_id").size()
        repeated_count = int(sum(count for receiver, count in sender_pairs.items() if (sender, receiver) in repeated_pairs))
        no_response_rate = float(group["after_non_response"].mean())
        platform_count = int(group["platform"].nunique())
        receiver_count = int(group["receiver_id"].nunique())
        change = _frequency_change(sender_daily)
        messages_per_day = len(group) / period_days

        flags: list[str] = []
        if messages_per_day > 5:
            flags.append("High-frequency contact")
        elif messages_per_day > 2:
            flags.append("Medium-frequency contact")
        else:
            flags.append("Low-frequency contact")
        if repeated_count:
            flags.append("Repeated-contact pattern")
        if change >= 0.5 and len(group) >= 4:
            flags.append("Increasing-frequency pattern")
        if any((sender, receiver) in cross_platform_pairs for receiver in sender_pairs.index):
            flags.append("Cross-platform pattern")
        if receiver_count >= 2:
            flags.append("Multiple-account contact pattern")
        if no_response_rate >= 0.5 and len(group) >= 2:
            flags.append("Contact attempts marked unanswered")

        if messages_per_day > 5 or (repeated_count >= 6 and no_response_rate >= 0.5):
            level = "High-risk communication pattern"
        elif repeated_count or change >= 0.5 or platform_count > 1 or receiver_count >= 2 or no_response_rate >= 0.5:
            level = "Elevated indicator"
        elif messages_per_day > 2:
            level = "Pattern detected"
        else:
            level = "Low concern"

        sender_summaries.append({
            "sender_id": sender,
            "message_count": int(len(group)),
            "messages_per_day": round(messages_per_day, 2),
            "repeated_contacts": repeated_count,
            "unanswered_rate": round(no_response_rate, 2),
            "platform_count": platform_count,
            "receiver_count": receiver_count,
            "frequency_change": change,
            "risk_level": level,
            "indicators": flags,
            "ml_anomaly": False,
        })
        # response_delay is a documented proxy: no response duration exists in the input schema.
        features.append([messages_per_day, repeated_count, no_response_rate, platform_count, change, receiver_count])

    ml_available = False
    ml_note = "Machine-learning analysis needs at least five distinct senders."
    if len(sender_summaries) >= 5:
        try:
            from sklearn.ensemble import IsolationForest

            model = IsolationForest(n_estimators=100, contamination="auto", random_state=42)
            predictions = model.fit_predict(np.asarray(features, dtype=float))
            for summary, prediction in zip(sender_summaries, predictions):
                summary["ml_anomaly"] = bool(prediction == -1)
            ml_available = True
            ml_note = "Isolation Forest flags outliers for review; it does not decide whether behaviour is harmful."
        except (ImportError, ValueError) as error:
            ml_note = f"Machine-learning signal unavailable: {error.__class__.__name__}. Rule indicators remain available."

    level_counts = Counter(summary["risk_level"] for summary in sender_summaries)
    indicators = Counter(flag for summary in sender_summaries for flag in summary["indicators"])
    combined = data.merge(
        pd.DataFrame(sender_summaries)[["sender_id", "risk_level"]],
        on="sender_id",
        how="left",
    )
    combined["timestamp"] = combined["timestamp"].dt.strftime("%Y-%m-%d %H:%M UTC")
    combined = combined.sort_values("timestamp", ascending=False)
    log_records = combined[[
        "timestamp", "sender_id", "receiver_id", "platform", "message_type",
        "response_status", "risk_level", "repeated_contact", "after_non_response", "cross_platform",
    ]].replace({np.nan: None}).to_dict(orient="records")

    high_count = level_counts.get("High-risk communication pattern", 0)
    elevated_count = level_counts.get("Elevated indicator", 0)
    if high_count:
        summary_text = f"{high_count} sender profile(s) show a high-risk communication pattern based on the configured rules. Review the underlying records and context."
    elif elevated_count:
        summary_text = f"{elevated_count} sender profile(s) have elevated indicators. These are observable data patterns, not conclusions about intent."
    else:
        summary_text = "No elevated rule-based indicators were found in this dataset. This does not establish that all contact is wanted."

    return {
        "total_messages": int(len(data)),
        "unique_accounts": int(pd.concat([data["sender_id"], data["receiver_id"]]).nunique()),
        "average_per_day": round(len(data) / period_days, 2),
        "repeated_contact_count": int(data["repeated_contact"].sum()),
        "period_start": first_day.strftime("%Y-%m-%d"),
        "period_end": last_day.strftime("%Y-%m-%d"),
        "period_days": period_days,
        "summary": summary_text,
        "indicators": [{"name": name, "count": count} for name, count in indicators.most_common()],
        "risk_distribution": [{"name": name, "count": count} for name, count in level_counts.items()],
        "daily_counts": [{"day": day, "count": int(count)} for day, count in daily.items()],
        "sender_counts": [{"sender": sender, "count": int(count)} for sender, count in data.groupby("sender_id").size().sort_values(ascending=False).items()],
        "platform_counts": [{"platform": platform, "count": int(count)} for platform, count in data.groupby("platform").size().items()],
        "sender_summaries": sender_summaries,
        "logs": log_records,
        "ml_available": ml_available,
        "ml_note": ml_note,
    }
