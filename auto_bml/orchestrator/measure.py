"""
Measure phase: find runs >= 6h old → pull metrics → score → update hypotheses → open PR.
"""
import anthropic

from .. import config as cfg
from .. import pull_io, run_store, github_ops, scoring
from ..ads import client as ads_client, campaign as ads_campaign, metrics as ads_metrics
from ..models import BmlResult, RunStatus, PullHypothesis

_LEARN_PROMPT = """You are updating a PULL framework hypothesis based on Google Ads data.

Startup context:
{program}

Tested hypothesis:
- project: {project}
- urgency: {urgency}
- look: {look}
- lacking: {lacking}

Ad performance:
- Impressions: {impressions}
- Clicks: {clicks}
- Avg CPC: ${cpc:.2f}
- Conversion rate: {cvr:.1%}
- PULL score: {score}/5

Based on this market response, suggest refined values for each PULL variable.
If a variable performed well (high CTR, high CPC), keep it tight.
If poorly, broaden or reframe.

Return ONLY valid JSON:
{{"project": "...", "urgency": "...", "look": "...", "lacking": "..."}}
"""


def _refine_hypothesis(
    current: PullHypothesis,
    metrics,
    score: float,
    program: str,
    api_key: str,
) -> PullHypothesis:
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _LEARN_PROMPT.format(
        program=program or "Not provided.",
        project=current.project,
        urgency=current.urgency,
        look=current.look,
        lacking=current.lacking,
        impressions=metrics.impressions,
        clicks=metrics.clicks,
        cpc=metrics.average_cpc_usd,
        cvr=metrics.conversion_rate,
        score=score,
    )
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    import json
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)
    return PullHypothesis(**data)


def run() -> None:
    config = cfg.load()
    runs = run_store.load()
    ready = run_store.find_ready_runs(runs)

    if not ready:
        print("No runs ready for measurement.")
        return

    program = pull_io.read_program()
    client = ads_client.get_client(config)

    for run in ready:
        print(f"Measuring run {run.run_id}...")
        try:
            metrics = ads_metrics.fetch(
                client,
                config.google_ads_customer_id,
                run.campaign_id,
                run.started_at.date(),
            )
            score = scoring.pull_score(metrics)
            print(f"  PULL score: {score}/5 | clicks: {metrics.clicks} | CPC: ${metrics.average_cpc_usd:.2f}")

            updated_hypothesis = _refine_hypothesis(
                run.pull_snapshot, metrics, score, program, config.anthropic_api_key
            )
            pull_io.write_hypothesis(updated_hypothesis)

            run.metrics = metrics
            run.pull_score = score
            run.status = RunStatus.measured
            run_store.update(run)

            ads_campaign.pause_campaign(client, config.google_ads_customer_id, run.campaign_id)

            result = BmlResult(
                run=run,
                updated_hypothesis=updated_hypothesis,
                pull_score=score,
            )
            pr_url = github_ops.open_results_pr(result)
            result.pr_url = pr_url
            print(f"  PR opened: {pr_url}")

        except Exception as e:
            run.status = RunStatus.failed
            run_store.update(run)
            print(f"  Failed: {e}")
            raise
