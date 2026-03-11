from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path
    data: Path
    raw: Path
    interim: Path
    processed: Path
    artifacts: Path
    reports: Path

    @classmethod
    def default(cls) -> "Paths":
        root = Path(__file__).resolve().parents[1]
        data = root / "data"
        return cls(
            root=root,
            data=data,
            raw=data / "raw",
            interim=data / "interim",
            processed=data / "processed",
            artifacts=root / "artifacts",
            reports=root / "reports",
        )

    def ensure(self) -> None:
        for path in [self.data, self.raw, self.interim, self.processed, self.artifacts, self.reports]:
            path.mkdir(parents=True, exist_ok=True)
