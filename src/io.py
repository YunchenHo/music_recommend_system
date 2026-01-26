from pathlib import Path
from typing import Optional

import pandas as pd


def load_csv(path: Path, encoding: Optional[str] = None) -> pd.DataFrame:
    return pd.read_csv(path, encoding=encoding) if encoding else pd.read_csv(path)


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        if path.exists():
            return pd.read_parquet(path)
        csv_fallback = path.with_suffix(".csv")
        return pd.read_csv(csv_fallback)
    return pd.read_csv(path)


def save_df(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        try:
            df.to_parquet(path, index=False)
            return
        except Exception:
            # Fallback to CSV if parquet engine is not available.
            fallback = path.with_suffix(".csv")
            df.to_csv(fallback, index=False)
            return
    df.to_csv(path, index=False)
