"""Load the immutable AugustPounds history and merge current GBPCNY checkpoints.

The raw '发布日期' values are intentionally NOT time-zone converted or edited.
A newer GBPCNY observation wins if the two archives share an issue timestamp.
"""
import gzip
import hashlib
import io
from pathlib import Path

import pandas as pd

SEED_PATH = Path("data/history_2023_2026.csv.gz")
CHECKPOINT_PATH = Path("Formal Art/send.csv")
EXPECTED_SOURCE_SHA256 = "e351207ea8c87ddf0a4e4387dafbb6d91ec64656129a2439015404523f38de66"
REQUIRED_COLUMNS = [
    "货币名称", "现汇买入价", "现钞买入价", "现汇卖出价",
    "现钞卖出价", "中行折算价", "发布日期", "发布时间",
]


def load_historical_data():
    # Do not silently start a new series from 2026 if the seed is absent.
    with gzip.open(SEED_PATH, "rb") as archive:
        raw = archive.read()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("The historical CSV seed was modified or corrupted")

    historical = pd.read_csv(io.BytesIO(raw), encoding="utf16")
    if list(historical.columns) != REQUIRED_COLUMNS or len(historical) != 82088:
        raise RuntimeError("The 2023 historical seed has unexpected contents")

    sources = [historical]
    checkpoint_rows = 0
    if CHECKPOINT_PATH.exists():
        checkpoint = pd.read_csv(CHECKPOINT_PATH, encoding="utf16")
        if list(checkpoint.columns) != REQUIRED_COLUMNS:
            raise RuntimeError("GBPCNY checkpoint schema does not match historical data")
        checkpoint_rows = len(checkpoint)
        sources.append(checkpoint)

    # Keep data types and timestamp values unchanged; prefer the new checkpoint
    # when both sources contain the same published timestamp.
    data = pd.concat(sources, ignore_index=True)
    dates = pd.to_datetime(data["发布日期"], errors="coerce")
    rates = pd.to_numeric(data["现汇卖出价"], errors="coerce")
    if dates.isna().any() or rates.isna().any():
        raise RuntimeError("Invalid price or timestamp in merged GBPCNY data")

    data = data.drop_duplicates(subset=["发布日期"], keep="last")
    data = data.sort_values("发布日期", kind="mergesort").reset_index(drop=True)
    if pd.to_datetime(data["发布日期"]).min().year != 2023:
        raise RuntimeError("Historical start date is missing after merge")

    latest_price = float(pd.to_numeric(data["现汇卖出价"]).iloc[-1])
    earliest = pd.to_datetime(data["发布日期"].iloc[0])
    latest = pd.to_datetime(data["发布日期"].iloc[-1])
    print(
        "Historical restore: seed={}, checkpoint={}, merged={}, "
        "range={} to {} (UTC+8), latest_price={}".format(
            len(historical), checkpoint_rows, len(data), earliest, latest, latest_price
        ),
        flush=True,
    )
    return data, latest_price
