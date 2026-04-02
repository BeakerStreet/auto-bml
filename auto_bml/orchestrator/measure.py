"""
Measure phase: find runs >= 6h → pull metrics → score → update state
→ advance phase if converged → warn on local minima → open PR.
"""
import json

import anthropic

from .. import config as cfg
from .. import pull_io, run_store, github_ops, scoring, phase as phase_mod
from ..ads import client as ads_client, campaign as ads_campaign, metrics as ads_metrics
from ..models import BmlResult, Phase, PullHypothesis, RunStatus

_LEARN_PROMPT = """You are refining one variable in a PULL framework hypothesis based on Google Ads data.

Startup context:
{program}

Current phase: {phase} (optimising '{active_var}' only)
Primary metric for this phase: {primary_metric}

Tested hypothesis:
- project: {project}
- urgency: {urgency}
- look: {look}
- lacking: {lacking}

Ad performance:
- Impressions: {impressions}
- Clicks: {clicks}
- CTR: {ctr:.2%}
- Avg CPC: ${cpc:.2f}
- Conversion rate: {cvr:.1%}
- PULL score: {score}/5

LOCKED variables (do not change these — reproduce exactly):
{locked_lines}

Based on market response, suggest a refined value for '{active_var}' only.
If performance was strong (high {primary_metric}), tighten the framing.
If weak, broaden or reframe.

Return ONLY valid JSON with all four keys — locked values reproduced verbatim:
{{"project": "...", "urgency": "...", "look": "...", "lacking": "..."}}
"""


def _refine_hypothesis(
    current: PullHypothesis,
    state,
    metrics,
    score: float,
    program: str,
    api_key: str,
) -> PullHypothesis:
    client = anthropic.Anthropic(api_key=api_key)

    active_var = state.phase.variable()
    locked_lines = "\n".join(
        f"  {k}: {v}" for k, v in state.locked.items() if k != active_var
    ) or "  (none)"

    ctr = metrics.clicks / metrics.impressions if metrics.impressions else 0.0

    prompt = _LEARN_PROMPT.format(
        program=program or "Not provided.",
        phase=state.phase.value,
        active_var=active_var,
        primary_metric=state.phase.primary_metric(),
        project=current.project,
        urgency=current.urgency,
        look=current.look,
        lacking=current.lacking,
        impressions=metrics.impressions,
        clicks=metrics.clicks,
        ctr=ctr,
        cpc=metrics.average_cpc_usd,
        cvr=metrics.conversion_rate,
        score=score,
        locked_lines=locked_lines,
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

    # Enforce locked variables — do not allow agent to drift them
    for var, val in state.locked.items():
        data[var] = val

    return PullHypothesis(**data)


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
        print(f"Measuring run {run.run_id} (phase: {run.phase.value})...")
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

            # Update state with this run's result
            state = phase_mod.update_state(state, metrics, score)
            warning = phase_mod.local_minima_warning(state)
            if warning:
                print(f"  ⚠ Local minima warning: {warning}")

            # Refine hypothesis for the active variable
            updated_hypothesis = _refine_hypothesis(
                run.pull_snapshot, state, metrics, score, program, config.anthropic_api_key
            )

            # Check convergence and advance phase if warranted
            phase_advanced = False
            if phase_mod.should_advance(state):
                best_value = getattr(updated_hypothesis, state.phase.variable())
                print(f"  Phase {state.phase.value} converged. Locking '{state.phase.variable()}' = '{best_value[:50]}'")
                state = phase_mod.advance_phase(state, best_value)
                phase_advanced = True
                if state.phase.next() is None and not phase_advanced:
                    print("  All phases complete. BML loop finished.")

            pull_io.append_result(updated_hypothesis, run.run_id, run.phase.value, score)
            run_store.save_state(state)

            run.metrics = metrics
            run.pull_score = score
            run.status = RunStatus.measured
            run_store.update(run)

            ads_campaign.pause_campaign(
                ads_client_instance, config.google_ads_customer_id, run.campaign_id
            )

            result = BmlResult(
                run=run,
                updated_hypothesis=updated_hypothesis,
                pull_score=score,
                local_minima_warning=warning,
                phase_advanced=phase_advanced,
            )
            pr_url = github_ops.open_results_pr(result)
            result.pr_url = pr_url
            print(f"  PR: {pr_url}")

        except Exception as e:
            run.status = RunStatus.failed
            run_store.update(run)
            print(f"  Failed: {e}")
            raise
