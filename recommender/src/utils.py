from pathlib import Path


def resolve_input_path(path: Path, raw_dir: Path, filename: str) -> Path:
    if path.exists():
        return path

    candidate = raw_dir / filename
    if candidate.exists():
        return candidate

    matches = list(raw_dir.rglob(filename))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise FileNotFoundError(f"Multiple matches for {filename}: {matches}")

    raise FileNotFoundError(f"Could not find {filename} under {raw_dir}")
