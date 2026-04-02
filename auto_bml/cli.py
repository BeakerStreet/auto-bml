import click


@click.group()
def cli():
    pass


@cli.command()
def launch():
    """Generate copy, deploy, and launch a Google Ads campaign."""
    from .orchestrator import launch
    launch.run()


@cli.command()
def measure():
    """Check for completed runs, pull metrics, score, and open a PR."""
    from .orchestrator import measure
    measure.run()


@cli.command()
def onboard():
    """One-time setup: read .env, OAuth, push secrets to GitHub, scaffold files."""
    from .ads import onboarding
    onboarding.run()


if __name__ == "__main__":
    cli()
