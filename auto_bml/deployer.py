from abc import ABC, abstractmethod

import requests

from .models import PageCopy


class DeployProvider(ABC):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    @abstractmethod
    def deploy(self, copy: PageCopy, stripe_link: str) -> str:
        """Trigger a deploy and return the live URL."""


class VercelProvider(DeployProvider):
    def deploy(self, copy: PageCopy, stripe_link: str) -> str:
        payload = {
            "env": {
                "BML_HEADLINE": copy.headline,
                "BML_SUBHEADLINE": copy.subheadline,
                "BML_BODY": copy.body,
                "BML_CTA": copy.cta,
                "BML_CTA_URL": stripe_link,
            }
        }
        resp = requests.post(self.webhook_url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("url") or data.get("deploymentUrl") or self.webhook_url


class NetlifyProvider(DeployProvider):
    def deploy(self, copy: PageCopy, stripe_link: str) -> str:
        import json
        from pathlib import Path

        Path("bml_copy.json").write_text(json.dumps({
            **copy.model_dump(),
            "cta_url": stripe_link,
        }, indent=2))

        resp = requests.post(self.webhook_url, timeout=30)
        resp.raise_for_status()
        return self.webhook_url


def get_provider(provider: str, webhook_url: str) -> DeployProvider:
    if provider.lower() == "vercel":
        return VercelProvider(webhook_url)
    if provider.lower() == "netlify":
        return NetlifyProvider(webhook_url)
    raise ValueError(f"Unknown deploy provider: {provider!r}. Use 'vercel' or 'netlify'.")
