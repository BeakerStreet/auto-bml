"""
Measure: pull metrics → score → ask Claude which variable to work on next
→ update pull.csv → open PR.

The agent picks the variable it judges most worth improving based on the
full run history. P/U/L → ad iterations; Lacking → landing page iterations.
"""
import json

import anthropic

from .. import config as cfg
from .. import pull_io, run_store, github_ops, scoring
from ..ads import client as ads_client, campaign as ads_campaign, metrics as ads_metrics
from ..models import PULL_VARIABLES, BmlResult, BmlState, PullHypothesis, RunStatus

_LEARN_PROMPT = """You are improving a PULL framework hypothesis based on Google Ads data.

PULL variables:
- project: the specific job the customer is trying to complete
- urgency: why they can't ignore it right now
- look: what solutions they're currently evaluating
- lacking: where those solutions fall short (tested via landing page, not ads)

Startup context:
{program}

Current hypothesis:
- project: {project}
- urgency: {urgency}
- look: {look}
- lacking: {lacking}

This run tested variable '{active_variable}'. Ad performance:
- Impressions: {impressions}
- Clicks: {clicks}
- CTR: {ctr:.2%}
- Avg CPC: ${cpc:.2f}
- Conversion rate: {cvr:.1%}
- PULL score: {score}/5

Run history (most recent first):
{history}

Based on the data, decide:
1. Which single variable would most improve the PULL score next iteration?
2. What should its new value be?
3. Should any variables be locked (confident they're well-defined)?

Return ONLY valid JSON:
{{
  "next_variable": "project|urgency|look|lacking",
  "project": "...",
  "urgency": "...",
  "look": "...",
  "lacking": "...",
  "lock": ["variable_name", ...]
}}

Rules:
- Only change the variable you select as next_variable
- Reproduce all other variables exactly as given above
- lock should list variables you're confident are well-defined (can be empty)
- lacking can only be tested via landing page; choose it when P/U/L signal is strong
"""


def _build_history(runs) -> str:
    measured = [r for r in runs if r.pull_score is not None][-10:]
    if not measured:
        return "No prior runs."
    lines = []
    for r in reversed(measured):
        m = r.metrics
        ctr = f"{m.clicks/m.impressions:.2%}" if m and m.impressions else "—"
        lines.append(
            f"  {r.run_id} | var={r.active_variable} | score={r.pull_score} | CTR={ctr} | CPC=${m.average_cpc_usd:.2f}" if m
            else f"  {r.run_id} | var={r.active_variable} | score={r.pull_score}"
        )
    return "\n".join(lines)



def run() -> None:
    config = cfg.load()
    runs = run_store.load()
    ready = run_store.find_ready_runs(runs)

    if not ready:
        print("No runs ready for measurement.")
        return

    program = pull_io.read_program()
    ads_client_instance = ads_client.get_client(config)
    state = run_store.load_state()

    for run in ready:
        print(f"Measuring run {run.run_id} (active: {run.active_variable})...")
        try:
            metrics = ads_metrics.fetch(
                ads_client_instance,
                config.google_ads_customer_id,
                run.campaign_id,
                run.started_at.date(),
            )
            score = scoring.pull_score(metrics)
            ctr = metrics.clicks / metrics.impressions if metrics.impressions else 0.0
            print(f"  Score: {score}/5 | CTR: {ctr:.2%} | CPC: ${metrics.average_cpc_usd:.2f} | CVR: {metrics.conversion_rate:.1%}")

            run.metrics = metrics
            run.pull_score = score
            run.status = RunStatus.measured
            run_store.update(run)

            # Ask Claude which variable to improve next
            hypothesis = run.pull_snapshot
            history = _build_history(run_store.load())

            client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            prompt = _LEARN_PROMPT.format(
                program=program or "Not provided.",
                project=hypothesis.project,
                urgency=hypothesis.urgency,
                look=hypothesis.look,
                lacking=hypothesis.lacking,
                active_variable=run.active_variable,
                impressions=metrics.impressions,
                clicks=metrics.clicks,
                ctr=ctr,
                cpc=metrics.average_cpc_usd,
                cvr=metrics.conversion_rate,
                score=score,
                history=history,
            )
            message = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)

            next_variable = data.get("next_variable", run.active_variable)
            if next_variable not in PULL_VARIABLES:
                next_variable = run.active_variable

            updated_hypothesis = PullHypothesis(
                project=data.get("project", hypothesis.project),
                urgency=data.get("urgency", hypothesis.urgency),
                look=data.get("look", hypothesis.look),
                lacking=data.get("lacking", hypothesis.lacking),
            )

            # Update locked variables
            new_state = BmlState(
                active_variable=next_variable,
                locked={**state.locked, **{v: getattr(updated_hypothesis, v) for v in data.get("lock", [])}},
            )
            run_store.save_state(new_state)

            pull_io.append_result(updated_hypothesis, run.run_id, run.active_variable, score)

            ads_campaign.pause_campaign(
                ads_client_instance, config.google_ads_customer_id, run.campaign_id
            )

            mode = "landing page" if next_variable == "lacking" else "ads"
            print(f"  Next: iterate '{next_variable}' via {mode}")

            result = BmlResult(
                run=run,
                updated_hypothesis=updated_hypothesis,
                pull_score=score,
            )
            pr_url = github_ops.open_results_pr(result)
            print(f"  PR: {pr_url}")

        except Exception as e:
            run.status = RunStatus.failed
            run_store.update(run)
            print(f"  Failed: {e}")
            raise
