"""
GitHub Pages deployer.

Commits docs/index.html to the repo via GitHub API.
GitHub Pages rebuilds automatically on push.
"""
from github import Github, UnknownObjectException

from .config import Config
from .models import PageCopy

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{headline}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #fff;
      color: #111;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 2rem;
    }
    main { max-width: 600px; width: 100%; }
    h1 {
      font-size: clamp(1.8rem, 5vw, 3rem);
      line-height: 1.1;
      font-weight: 800;
      margin: 0 0 1rem;
    }
    .sub {
      font-size: 1.2rem;
      color: #444;
      line-height: 1.4;
      margin: 0 0 1.25rem;
    }
    .body {
      font-size: 1rem;
      color: #555;
      line-height: 1.7;
      margin: 0 0 2rem;
    }
    .cta {
      display: inline-block;
      background: #111;
      color: #fff;
      padding: 0.85rem 2rem;
      border-radius: 6px;
      text-decoration: none;
      font-weight: 600;
      font-size: 1rem;
    }
    .cta:hover { opacity: 0.8; }
  </style>
</head>
<body>
  <main>
    <h1>{headline}</h1>
    <p class="sub">{subheadline}</p>
    <p class="body">{body}</p>
    <a href="#" class="cta">{cta}</a>
  </main>
</body>
</html>
"""


def _render_html(copy: PageCopy) -> str:
    return (
        _HTML_TEMPLATE
        .replace("{headline}", copy.headline)
        .replace("{subheadline}", copy.subheadline)
        .replace("{body}", copy.body)
        .replace("{cta}", copy.cta)
    )


class GitHubPagesProvider:
    def __init__(self, github_token: str, repo: str):
        self.github_token = github_token
        self.repo = repo  # "owner/repo"

    def deploy(self, copy: PageCopy) -> str:
        html = _render_html(copy)
        g = Github(self.github_token)
        repo = g.get_repo(self.repo)
        path = "docs/index.html"
        try:
            existing = repo.get_contents(path)
            repo.update_file(path, "bml: update landing page copy", html, existing.sha)
        except UnknownObjectException:
            repo.create_file(path, "bml: create landing page", html)
        owner, name = self.repo.split("/")
        return f"https://{owner}.github.io/{name}"


def get_provider(config: Config) -> GitHubPagesProvider:
    return GitHubPagesProvider(
        github_token=config.github_token,
        repo=config.github_repository,
    )
