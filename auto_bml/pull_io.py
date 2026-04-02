import csv
from pathlib import Path

from .models import PullHypothesis

PULL_CSV = Path("pull.csv")
PROGRAM_MD = Path("program.md")

HEADERS = ["run_id", "variable", "impressions", "ctr", "cvr", "project", "urgency", "look", "lacking"]


def read_hypothesis() -> PullHypothesis:
    """Returns the most recent hypothesis row (last non-empty row)."""
    if not PULL_CSV.exists():
        return PullHypothesis()
    with PULL_CSV.open() as f:
        reader = csv.DictReader(f)
        last = None
        for row in reader:
            if any(row.get(h, "").strip() for h in ["project", "urgency", "look", "lacking"]):
                last = row
    if last is None:
        return PullHypothesis()
    return PullHypothesis(
        project=last.get("project", "").strip(),
        urgency=last.get("urgency", "").strip(),
        look=last.get("look", "").strip(),
        lacking=last.get("lacking", "").strip(),
    )


def append_result(
    hypothesis: PullHypothesis,
    run_id: str,
    variable: str,
    impressions: int,
    ctr: float,
    cvr: float,
) -> None:
    """Appends a new row — every iteration is preserved as a record."""
    write_header = not PULL_CSV.exists() or PULL_CSV.stat().st_size == 0
    with PULL_CSV.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "run_id": run_id,
            "variable": variable,
            "impressions": impressions,
            "ctr": f"{ctr:.2%}",
            "cvr": f"{cvr:.2%}",
            **hypothesis.model_dump(),
        })


def read_program() -> str:
    if not PROGRAM_MD.exists():
        return ""
    return PROGRAM_MD.read_text().strip()


def read_stripe_link() -> str:
    if not PROGRAM_MD.exists():
        return ""
    for line in PROGRAM_MD.read_text().splitlines():
        line = line.strip()
        if line.startswith("https://buy.stripe.com") or line.startswith("https://stripe.com"):
            return line
    return ""
