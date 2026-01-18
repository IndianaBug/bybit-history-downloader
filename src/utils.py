import gzip
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple


def gunzip_file(
    gz_path: str | Path,
    *,
    delete_original: bool = True,
) -> Path:
    gz_path = Path(gz_path)
    out_path = gz_path.with_suffix("")  # removes .gz

    with gzip.open(gz_path, "rb") as f_in, open(out_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    if delete_original:
        gz_path.unlink()

    return out_path


def split_date_range(
    start_date: str,
    end_date: str,
    n: int,
) -> List[Tuple[str, str]]:
    """
    Split an inclusive date range [start_date, end_date] into chunks of at most n days.

    - Dates MUST be in 'YYYY-MM-DD' format (zero-padded).
    - Raises ValueError on invalid format or logical errors.
    """
    _DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if not _DATE_RE.match(start_date):
        raise ValueError(f"start_date must be 'YYYY-MM-DD' (got {start_date!r})")
    if not _DATE_RE.match(end_date):
        raise ValueError(f"end_date must be 'YYYY-MM-DD' (got {end_date!r})")

    if n <= 0:
        raise ValueError("n must be a positive integer (days per chunk)")

    fmt = "%Y-%m-%d"

    try:
        start = datetime.strptime(start_date, fmt).date()
        end = datetime.strptime(end_date, fmt).date()
    except ValueError as e:
        # Catches invalid dates like 2026-02-30
        raise ValueError(f"Invalid date value: {e}") from None

    if start > end:
        raise ValueError("start_date must be <= end_date")

    out: List[Tuple[str, str]] = []
    cur = start

    while cur <= end:
        chunk_end = min(cur + timedelta(days=n - 1), end)
        out.append((cur.strftime(fmt), chunk_end.strftime(fmt)))
        cur = chunk_end + timedelta(days=1)

    return out
