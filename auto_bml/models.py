from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PullHypothesis(BaseModel):
    project: str = ""
    urgency: str = ""
    look: str = ""
    lacking: str = ""


class PageCopy(BaseModel):
    headline: str
    subheadline: str
    body: str
    cta: str
    ad_headlines: list[str] = Field(min_length=3, max_length=5)
    ad_descriptions: list[str] = Field(min_length=2, max_length=4)
    keywords: list[str]


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
    pr_url: Optional[str] = None
