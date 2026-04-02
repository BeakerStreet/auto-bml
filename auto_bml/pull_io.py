import csv
from pathlib import Path

from .models import PullHypothesis

PULL_CSV = Path("pull.csv")
PROGRAM_MD = Path("program.md")

HEADERS = ["project", "urgency", "look", "lacking"]


def read_hypothesis() -> PullHypothesis:
    if not PULL_CSV.exists():
        return PullHypothesis()
    with PULL_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if any(row.get(h, "").strip() for h in HEADERS):
                return PullHypothesis(
                    project=row.get("project", "").strip(),
                    urgency=row.get("urgency", "").strip(),
                    look=row.get("look", "").strip(),
                    lacking=row.get("lacking", "").strip(),
                )
    return PullHypothesis()


def write_hypothesis(hypothesis: PullHypothesis) -> None:
    with PULL_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerow(hypothesis.model_dump())


def read_program() -> str:
    if not PROGRAM_MD.exists():
        return ""
    return PROGRAM_MD.read_text().strip()
