from __future__ import annotations

import random
import time
from pathlib import Path
import re
from typing import Iterable

import numpy as np
import pandas as pd
import requests

WD_SPARQL = "https://query.wikidata.org/sparql"


def _default_cache_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "isrc",
            "wd_qid",
            "label_zh",
            "desc_zh",
            "label_en",
            "desc_en",
            "typeLabel",
        ]
    )


def load_cache(path: Path) -> pd.DataFrame:
    if path.exists():
        df = pd.read_parquet(path)
        for col in _default_cache_frame().columns:
            if col not in df.columns:
                df[col] = None
        return df
    return _default_cache_frame()


def save_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def build_isrc_query(isrc_batch: Iterable[str]) -> str:
    values = " ".join(f'"{str(x)}"' for x in isrc_batch)
    return f"""
    SELECT ?isrc ?item ?typeLabel ?label_zh ?desc_zh ?label_en ?desc_en WHERE {{
      VALUES ?isrc {{ {values} }}
      ?item wdt:P1243 ?isrc .

      OPTIONAL {{
        ?item rdfs:label ?label_zh .
        FILTER(LANG(?label_zh) = \"zh\")
      }}
      OPTIONAL {{
        ?item rdfs:label ?label_en .
        FILTER(LANG(?label_en) = \"en\")
      }}
      OPTIONAL {{
        ?item schema:description ?desc_zh .
        FILTER(LANG(?desc_zh) = \"zh\")
      }}
      OPTIONAL {{
        ?item schema:description ?desc_en .
        FILTER(LANG(?desc_en) = \"en\")
      }}

      OPTIONAL {{
        ?item wdt:P31 ?type .
        ?type rdfs:label ?typeLabel .
        FILTER(LANG(?typeLabel) = \"en\")
      }}
    }}
    """


def _sparql_request(
    session: requests.Session,
    query: str,
    timeout: int,
    max_retries: int,
) -> tuple[dict | None, str | None]:
    last_err = None
    for attempt in range(max_retries):
        try:
            r = session.get(
                WD_SPARQL, params={"query": query, "format": "json"}, timeout=timeout
            )
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {r.status_code}"
                time.sleep((2**attempt) + random.random())
                continue
            r.raise_for_status()
            return r.json(), None
        except Exception as exc:
            last_err = str(exc)
            time.sleep((2**attempt) + random.random())
    return None, last_err


def fetch_wikidata_by_isrc(
    isrc_list: Iterable[str],
    cache_path: Path,
    batch_size: int = 200,
    request_sleep: float = 1.0,
    max_retries: int = 4,
    timeout: int = 30,
    user_agent: str = "kkbox-class-project/0.1",
) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/sparql-results+json",
        }
    )

    cache_df = load_cache(cache_path)
    done = set(cache_df["isrc"].astype(str).tolist())
    todo = [str(x) for x in isrc_list if str(x) not in done]

    print(f"Cache already has {len(done)} rows. Todo: {len(todo)}")

    for start in range(0, len(todo), batch_size):
        batch = todo[start : start + batch_size]
        query = build_isrc_query(batch)
        data, err = _sparql_request(session, query, timeout=timeout, max_retries=max_retries)
        time.sleep(request_sleep + random.random() * 0.2)

        batch_rows: list[dict] = []
        if err:
            for isrc in batch:
                batch_rows.append(
                    {
                        "isrc": isrc,
                        "wd_qid": None,
                        "label_zh": None,
                        "desc_zh": None,
                        "label_en": None,
                        "desc_en": None,
                        "typeLabel": None,
                    }
                )
            print(f"[Batch {start//batch_size+1}] error: {err}")
        else:
            bindings = data.get("results", {}).get("bindings", [])
            seen: dict[str, dict] = {}
            for b in bindings:
                isrc = b.get("isrc", {}).get("value")
                item = b.get("item", {}).get("value")
                qid = item.rsplit("/", 1)[-1] if item else None
                if not isrc:
                    continue

                candidate = {
                    "isrc": isrc,
                    "wd_qid": qid,
                    "label_zh": b.get("label_zh", {}).get("value") or None,
                    "desc_zh": b.get("desc_zh", {}).get("value") or None,
                    "label_en": b.get("label_en", {}).get("value") or None,
                    "desc_en": b.get("desc_en", {}).get("value") or None,
                    "typeLabel": b.get("typeLabel", {}).get("value") or None,
                }

                if (isrc not in seen) or (
                    seen[isrc].get("desc_en") is None
                    and candidate.get("desc_en") is not None
                ):
                    seen[isrc] = candidate

            for isrc in batch:
                batch_rows.append(
                    seen.get(
                        isrc,
                        {
                            "isrc": isrc,
                            "wd_qid": None,
                            "label_zh": None,
                            "desc_zh": None,
                            "label_en": None,
                            "desc_en": None,
                            "typeLabel": None,
                        },
                    )
                )

        cache_df = pd.concat([cache_df, pd.DataFrame(batch_rows)], ignore_index=True)
        save_cache(cache_df, cache_path)

        got = cache_df["wd_qid"].notna().sum()
        processed = min(start + batch_size, len(todo))
        print(
            f"[Saved] total={len(cache_df)} matched={got} (processed {processed}/{len(todo)})"
        )

    print("Done. Cache saved to:", cache_path)
    return cache_df


def _uniq_join(series: pd.Series) -> str | pd.NA:
    vals = [str(x).strip() for x in series.dropna().tolist() if str(x).strip() != ""]
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return " || ".join(out) if out else pd.NA


def prepare_wikidata_matched_csv(
    cache_path: Path,
    out_dir: Path,
    lang: str = "en",
    add_features: bool = True,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    wd_cache = pd.read_parquet(cache_path)

    if lang == "en":
        cols = ["isrc", "wd_qid", "label_en", "desc_en", "typeLabel"]
    else:
        cols = ["isrc", "wd_qid", "label_zh", "desc_zh", "typeLabel"]

    cols = [c for c in cols if c in wd_cache.columns]
    wd = wd_cache[cols].copy()

    wd_matched = wd[wd["wd_qid"].notna()].copy()
    raw_path = out_dir / f"wikidata_isrc_matched_{lang}_raw.csv"
    wd_matched.to_csv(raw_path, index=False, encoding="utf-8-sig")

    agg_dict = {c: _uniq_join for c in cols if c != "isrc"}
    wd_by_isrc = wd_matched.groupby("isrc", as_index=False).agg(agg_dict)

    if add_features and lang == "en":
        def _safe_lower(x):
            return ("" if pd.isna(x) else str(x)).lower()

        wd_by_isrc["has_feat"] = wd_by_isrc.get("desc_en", pd.Series(dtype=object)).apply(
            lambda x: bool(re.search(r"\b(feat\.|featuring|ft\.?)\b", _safe_lower(x)))
        )
        wd_by_isrc["is_single"] = wd_by_isrc.get("typeLabel", pd.Series(dtype=object)).apply(
            lambda x: "single" in _safe_lower(x)
        )
        wd_by_isrc["has_vocal"] = wd_by_isrc.get("typeLabel", pd.Series(dtype=object)).apply(
            lambda x: "with vocals" in _safe_lower(x)
        )

    by_isrc_path = out_dir / f"wikidata_isrc_matched_{lang}_by_isrc.csv"
    wd_by_isrc.to_csv(by_isrc_path, index=False, encoding="utf-8-sig")

    print("Saved RAW:", raw_path, "rows:", len(wd_matched))
    print("Saved BY_ISRC:", by_isrc_path, "rows:", len(wd_by_isrc))
    return raw_path, by_isrc_path


def merge_wikidata_by_isrc(song_df: pd.DataFrame, wikidata_csv_path: Path) -> pd.DataFrame:
    wd_by_isrc = pd.read_csv(wikidata_csv_path)
    wd_by_isrc["isrc"] = wd_by_isrc["isrc"].astype("string").str.strip().str.upper()

    song_df = song_df.copy()
    if "isrc" in song_df.columns:
        song_df["isrc"] = song_df["isrc"].astype("string").str.strip().str.upper()

    merged = song_df.merge(wd_by_isrc, how="left", on="isrc")
    return merged
