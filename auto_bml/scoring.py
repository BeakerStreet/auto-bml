import math

from .models import AdsMetrics

# Normalization bounds derived from typical Google Ads search campaign ranges.
# raw = log10(monthly_volume_equiv * cpc_usd * (1 + competition_index))
# A campaign spending $20/day for 6 hours at $2 CPC with 0.5 competition
# produces roughly log10(60 * 2.0 * 1.5) = log10(180) ≈ 2.26
# Bounds set to cover the realistic range: near-zero to exceptional demand.
_RAW_MIN = 0.0   # ~log10(1) — effectively no signal
_RAW_MAX = 5.0   # ~log10(100,000) — exceptional, viral-level demand


def pull_score(metrics: AdsMetrics) -> float:
    """
    Converts AdsMetrics into a 1–5 logarithmic PULL score.

    Score of 5: customers spring-loaded, ripping product off shelf.
    Score of 1: no meaningful demand signal.

    Each step represents ~10x more demand intensity than the previous.
    """
    volume_equiv = max(metrics.clicks, 1)
    cpc = max(metrics.average_cpc_usd, 0.01)
    competition = metrics.competition_index

    raw = math.log10(volume_equiv * cpc * (1 + competition))
    normalized = (raw - _RAW_MIN) / (_RAW_MAX - _RAW_MIN)
    score = 1 + normalized * 4  # map [0, 1] → [1, 5]
    return round(max(1.0, min(5.0, score)), 2)
