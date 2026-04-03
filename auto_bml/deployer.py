from abc import ABC, abstractmethod

import requests

from .models import PageCopy


class DeployProvider(ABC):
    def __init__(self, webhook_url: str, site_url: str):
        self.webhook_url = webhook_url
        self.site_url = site_url

    @abstractmethod
    def deploy(self, copy: PageCopy, stripe_link: str) -> str:
        """Trigger a deploy and return the live URL."""


class VercelProvider(DeployProvider):
    def __init__(self, webhook_url: str, site_url: str, api_token: str, project_id: str):
        super().__init__(webhook_url, site_url)
        self.api_token = api_token
        self.project_id = project_id

    def deploy(self, copy: PageCopy, stripe_link: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_token}"}
        env_vars = {
            "BML_HEADLINE": copy.headline,
            "BML_SUBHEADLINE": copy.subheadline,
            "BML_BODY": copy.body,
            "BML_CTA": copy.cta,
            "BML_CTA_URL": stripe_link,
        }

        # Fetch existing env vars to get their IDs for updates
        resp = requests.get(
            f"https://api.vercel.com/v9/projects/{self.project_id}/env",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        existing = {e["key"]: e["id"] for e in resp.json().get("envs", [])}

        for key, value in env_vars.items():
            if key in existing:
                requests.patch(
                    f"https://api.vercel.com/v9/projects/{self.project_id}/env/{existing[key]}",
                    headers=headers,
                    json={"value": value},
                    timeout=30,
                ).raise_for_status()
            else:
                requests.post(
                    f"https://api.vercel.com/v9/projects/{self.project_id}/env",
                    headers=headers,
                    json={"key": key, "value": value, "type": "plain", "target": ["production"]},
                    timeout=30,
                ).raise_for_status()

        requests.post(self.webhook_url, timeout=30).raise_for_status()
        return self.site_url


class NetlifyProvider(DeployProvider):
    def deploy(self, copy: PageCopy, stripe_link: str) -> str:
        import json
        from pathlib import Path

        Path("bml_copy.json").write_text(json.dumps({
            **copy.model_dump(),
            "cta_url": stripe_link,
        }, indent=2))

        requests.post(self.webhook_url, timeout=30).raise_for_status()
        return self.site_url


def get_provider(config) -> DeployProvider:
    provider = config.deploy_provider.lower()
    if provider == "vercel":
        return VercelProvider(
            webhook_url=config.deploy_webhook_url,
            site_url=config.deploy_site_url,
            api_token=config.vercel_api_token,
            project_id=config.vercel_project_id,
        )
    if provider == "netlify":
        return NetlifyProvider(
            webhook_url=config.deploy_webhook_url,
            site_url=config.deploy_site_url,
        )
    raise ValueError(f"Unknown deploy provider: {config.deploy_provider!r}. Use 'vercel' or 'netlify'.")
