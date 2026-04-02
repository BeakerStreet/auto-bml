"""
Launch phase: read current PULL phase → generate phase-appropriate copy
→ deploy (only for LACKING phase) → create Google Ads campaign → store run metadata.
"""
import sys

from .. import config as cfg
from .. import pull_io, run_store, copywriter, deployer
from ..ads import client as ads_client, campaign as ads_campaign
from ..models import Phase, RunMetadata, RunStatus


def run() -> None:
    config = cfg.load()

    runs = run_store.load()
    active = [r for r in runs if r.status == RunStatus.running]
    if active:
        print(f"Warning: {len(active)} run(s) already in progress. Proceeding anyway.")

    hypothesis = pull_io.read_hypothesis()
    program = pull_io.read_program()
    state = run_store.load_state()

    if not any([hypothesis.project, hypothesis.urgency, hypothesis.look, hypothesis.lacking]):
        print("Error: pull.csv has no hypothesis. Fill in at least one variable.")
        sys.exit(1)

    print(f"Phase: {state.phase.value} (iteration {state.iterations_in_phase + 1})")
    print(f"Optimising: {state.phase.variable()} | metric: {state.phase.primary_metric()}")
    if state.locked:
        print(f"Locked: {', '.join(f'{k}={v[:30]}' for k, v in state.locked.items())}")

    client = ads_client.get_client(config)
    run = RunMetadata(phase=state.phase, pull_snapshot=hypothesis)

    if state.phase == Phase.LACKING:
        print("Generating landing page copy (LACKING phase)...")
        page_copy = copywriter.generate_page_copy(hypothesis, program, config.anthropic_api_key)
        print(f"  Headline: {page_copy.headline}")

        print("Deploying landing page...")
        provider = deployer.get_provider(config.deploy_provider, config.deploy_webhook_url)
        deploy_url = provider.deploy(page_copy)
        run.deploy_url = deploy_url
        print(f"  Deployed: {deploy_url}")

        # For LACKING phase we still need keywords; use locked look variable
        from ..models import AdCopy
        ad_copy = AdCopy(
            ad_headlines=["Solution to your problem", "Finally, what you need", "Built for your workflow"],
            ad_descriptions=["Stop settling for tools that almost work.", "The gap is finally filled."],
            keywords=[hypothesis.look] if hypothesis.look else ["solution"],
        )
    else:
        print(f"Generating ad copy (iterating '{state.phase.variable()}')...")
        ad_copy = copywriter.generate_ad_copy(hypothesis, state, program, config.anthropic_api_key)
        print(f"  Keywords: {', '.join(ad_copy.keywords[:5])}...")

    print("Creating Google Ads campaign...")
    campaign_resource = ads_campaign.create_experiment_campaign(
        client, config, run.run_id, ad_copy
    )
    run.campaign_id = campaign_resource

    run_store.append(run)
    print(f"Run {run.run_id} launched. Metrics collected in 6 hours.")
