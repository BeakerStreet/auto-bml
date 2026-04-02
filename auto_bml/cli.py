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
@click.option("--repo", required=True, help="GitHub repo in owner/name format")
@click.option("--github-token", envvar="GITHUB_TOKEN", required=True)
def onboard(repo, github_token):
    """One-time setup: Google Ads OAuth + push secrets to GitHub."""
    from .ads import onboarding
    onboarding.run(repo, github_token)


if __name__ == "__main__":
    cli()
