"""
Phase management for the PULL iteration hierarchy.

Validation order: PROJECT → URGENCY → LOOK → LACKING
- P, U, L1: ad copy iterations, primary signals are CTR and CPC
- L2 (LACKING): landing page iterations, primary signal is conversion rate

Convergence: advance phase when primary metric hasn't improved for
CONVERGENCE_THRESHOLD consecutive runs.

Local minima: warn (but don't act) when non-improving runs exceed
LOCAL_MINIMA_THRESHOLD, suggesting the human reframe the hypothesis
before the agent locks in a local optimum.
"""

from .models import AdsMetrics, BmlState, Phase

CONVERGENCE_THRESHOLD = 3   # consecutive non-improving runs → advance phase
LOCAL_MINIMA_THRESHOLD = 5  # non-improving runs before warning


def primary_metric_value(phase: Phase, metrics: AdsMetrics) -> float:
    if phase.primary_metric() == "ctr":
        if metrics.impressions == 0:
            return 0.0
        return metrics.clicks / metrics.impressions
    if phase.primary_metric() == "cpc":
        # Lower CPC is better (higher relevance score); invert so improvement = increase
        cpc = metrics.average_cpc_usd
        return 1 / cpc if cpc > 0 else 0.0
    if phase.primary_metric() == "conversion_rate":
        return metrics.conversion_rate
    return 0.0


def update_state(state: BmlState, metrics: AdsMetrics, pull_score: float) -> BmlState:
    """
    Returns an updated BmlState after a completed run.
    Does not mutate the input.
    """
    metric = primary_metric_value(state.phase, metrics)
    improved = metric > state.best_metric_in_phase

    new_state = state.model_copy(deep=True)
    new_state.iterations_in_phase += 1

    if improved:
        new_state.best_metric_in_phase = metric
        new_state.best_score_in_phase = pull_score
        new_state.non_improving_runs = 0
    else:
        new_state.non_improving_runs += 1

    return new_state


def should_advance(state: BmlState) -> bool:
    return state.non_improving_runs >= CONVERGENCE_THRESHOLD


def local_minima_warning(state: BmlState) -> str | None:
    if state.non_improving_runs < LOCAL_MINIMA_THRESHOLD:
        return None
    variable = state.phase.variable()
    return (
        f"Score for '{variable}' hasn't improved in {state.non_improving_runs} consecutive runs "
        f"(best: {state.best_score_in_phase}/5). "
        f"Consider manually reframing the '{variable}' hypothesis in pull.csv before continuing — "
        f"the agent may be stuck in a local optimum."
    )


def advance_phase(state: BmlState, best_value: str) -> BmlState:
    """
    Lock the current variable at its best value and move to the next phase.
    """
    new_state = state.model_copy(deep=True)
    new_state.locked[state.phase.variable()] = best_value
    next_phase = state.phase.next()
    if next_phase is None:
        return new_state  # LACKING was the last phase; stay put
    new_state.phase = next_phase
    new_state.iterations_in_phase = 0
    new_state.best_score_in_phase = 0.0
    new_state.best_metric_in_phase = 0.0
    new_state.non_improving_runs = 0
    return new_state
