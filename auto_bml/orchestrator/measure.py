"""
Measure: pull metrics → ask Claude which variable to work on next
→ update pull.csv → open PR.

Three metrics passed directly to Claude: impressions, CTR, CVR.
No derived score — Claude interprets the numbers.
"""
import json

import anthropic

from .. import config as cfg
from .. import pull_io, run_store, github_ops
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

This run tested variable '{active_variable}'. Results:
- Impressions: {impressions}
- CTR: {ctr}
- CVR: {cvr}

Run history (most recent first):
{history}

Based on the data, decide:
1. Which single variable would most benefit from iteration next?
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
- lacking is tested via landing page; only choose it when impressions and CTR are strong
"""


def _build_history(runs) -> str:
    measured = [r for r in runs if r.metrics is not None][-10:]
    if not measured:
        return "No prior runs."
    lines = []
    for r in reversed(measured):
        m = r.metrics
        lines.append(
            f"  {r.run_id} | var={r.active_variable} "
            f"| impressions={m.impressions} | CTR={m.ctr:.2%} | CVR={m.cvr:.2%}"
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
        print(f"Measuring run {run.run_id} (variable: {run.active_variable})...")
        try:
            metrics = ads_metrics.fetch(
                ads_client_instance,
                config.google_ads_customer_id,
                run.campaign_id,
                run.started_at.date(),
            )
            print(f"  impressions={metrics.impressions} | CTR={metrics.ctr:.2%} | CVR={metrics.cvr:.2%}")

            run.metrics = metrics
            run.status = RunStatus.measured
            run_store.update(run)

            hypothesis = run.pull_snapshot
            client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            message = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": _LEARN_PROMPT.format(
                    program=program or "Not provided.",
                    project=hypothesis.project,
                    urgency=hypothesis.urgency,
                    look=hypothesis.look,
                    lacking=hypothesis.lacking,
                    active_variable=run.active_variable,
                    impressions=metrics.impressions,
                    ctr=f"{metrics.ctr:.2%}",
                    cvr=f"{metrics.cvr:.2%}",
                    history=_build_history(run_store.load()),
                )}],
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

            new_state = BmlState(
                active_variable=next_variable,
                locked={**state.locked, **{v: getattr(updated_hypothesis, v) for v in data.get("lock", [])}},
            )
            run_store.save_state(new_state)

            pull_io.append_result(
                updated_hypothesis, run.run_id, run.active_variable,
                metrics.impressions, metrics.ctr, metrics.cvr,
            )

            ads_campaign.pause_campaign(
                ads_client_instance, config.google_ads_customer_id, run.campaign_id
            )

            mode = "landing page" if next_variable == "lacking" else "ads"
            print(f"  Next: '{next_variable}' via {mode}")

            pr_url = github_ops.open_results_pr(BmlResult(
                run=run,
                updated_hypothesis=updated_hypothesis,
            ))
            print(f"  PR: {pr_url}")

        except Exception as e:
            run.status = RunStatus.failed
            run_store.update(run)
            print(f"  Failed: {e}")
            raise
