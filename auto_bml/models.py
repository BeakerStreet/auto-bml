from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Phase(str, Enum):
    PROJECT = "PROJECT"
    URGENCY = "URGENCY"
    LOOK = "LOOK"
    LACKING = "LACKING"

    def next(self) -> Optional["Phase"]:
        order = [Phase.PROJECT, Phase.URGENCY, Phase.LOOK, Phase.LACKING]
        idx = order.index(self)
        return order[idx + 1] if idx + 1 < len(order) else None

    def variable(self) -> str:
        return self.value.lower()

    def primary_metric(self) -> str:
        return {
            Phase.PROJECT: "ctr",
            Phase.URGENCY: "ctr",
            Phase.LOOK: "cpc",
            Phase.LACKING: "conversion_rate",
        }[self]

    def uses_landing_page(self) -> bool:
        return self == Phase.LACKING


class BmlState(BaseModel):
    phase: Phase = Phase.PROJECT
    iterations_in_phase: int = 0
    best_score_in_phase: float = 0.0
    best_metric_in_phase: float = 0.0
    non_improving_runs: int = 0
    locked: dict[str, str] = Field(default_factory=dict)


class PullHypothesis(BaseModel):
    project: str = ""
    urgency: str = ""
    look: str = ""
    lacking: str = ""


class AdCopy(BaseModel):
    ad_headlines: list[str] = Field(min_length=3, max_length=5)
    ad_descriptions: list[str] = Field(min_length=2, max_length=4)
    keywords: list[str]


class PageCopy(BaseModel):
    headline: str
    subheadline: str
    body: str
    cta: str


class AdsMetrics(BaseModel):
    impressions: int
    clicks: int
    average_cpc_micros: int
    conversions: float
    competition_index: float  # 0.0–1.0

    @property
    def average_cpc_usd(self) -> float:
        return self.average_cpc_micros / 1_000_000

    @property
    def conversion_rate(self) -> float:
        if self.clicks == 0:
            return 0.0
        return self.conversions / self.clicks


class RunStatus(str, Enum):
    running = "running"
    measured = "measured"
    failed = "failed"


class RunMetadata(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    phase: Phase = Phase.PROJECT
    campaign_id: Optional[str] = None
    deploy_url: Optional[str] = None
    pull_snapshot: PullHypothesis = Field(default_factory=PullHypothesis)
    status: RunStatus = RunStatus.running
    pull_score: Optional[float] = None
    metrics: Optional[AdsMetrics] = None


class BmlResult(BaseModel):
    run: RunMetadata
    updated_hypothesis: PullHypothesis
    pull_score: float
    local_minima_warning: Optional[str] = None
    phase_advanced: bool = False
    pr_url: Optional[str] = None
