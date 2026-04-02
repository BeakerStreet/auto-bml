"""
Variable-aware copy generation.

project / urgency / look → ad copy (iterate active variable, lock the rest)
lacking → landing page copy (all four variables inform the page)
"""
import json

import anthropic

from .models import AdCopy, BmlState, PageCopy, PullHypothesis

_SYSTEM = """You are a direct-response copywriter who understands the PULL framework.
PULL means customers are already trying to solve a specific problem — your job is to
reflect their existing demand back at them, not to manufacture desire.

You are running a structured experiment. Only the variable marked ACTIVE should be
iterated. All LOCKED variables must be reproduced exactly as given."""

_AD_PROMPT = """Startup context:
{program}

PULL hypothesis — iterate ONLY the active variable:

  ACTIVE variable ({active_var}): {active_value}

  OTHER variables (reproduce exactly, do not rephrase):
{other_lines}

Generate Google Ads copy that tests the ACTIVE variable in isolation.

Return ONLY valid JSON:
{{
  "ad_headlines": ["...", "...", "..."],
  "ad_descriptions": ["...", "..."],
  "keywords": ["keyword 1", "...up to 20 keywords"]
}}

Constraints:
- ad_headlines: max 30 characters each, 3–5 required
- ad_descriptions: max 90 characters each, 2–4 required
- keywords: phrase match, directly derived from the active variable and look hypothesis
"""

_PAGE_PROMPT = """Startup context:
{program}

PULL hypothesis (write landing page to address LACKING):
- project: {project}
- urgency: {urgency}
- look: {look}
- lacking (ACTIVE — this is what the page must address): {lacking}

Write landing page copy that fulfils the promise of the ad.
A visitor who clicked because of genuine demand should feel: "this was built for me."

Return ONLY valid JSON:
{{
  "headline": "...",
  "subheadline": "...",
  "body": "2-3 sentences max",
  "cta": "..."
}}
"""


def generate_ad_copy(
    hypothesis: PullHypothesis,
    state: BmlState,
    program: str,
    api_key: str,
) -> AdCopy:
    active_var = state.active_variable
    active_value = getattr(hypothesis, active_var) or "not yet defined"

    other_lines = "\n".join(
        f"  {var}: {getattr(hypothesis, var) or 'not yet defined'}"
        for var in ["project", "urgency", "look"]
        if var != active_var
    )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _AD_PROMPT.format(
        program=program or "Not provided.",
        active_var=active_var,
        active_value=active_value,
        other_lines=other_lines,
    )
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return AdCopy(**json.loads(_strip_fences(message.content[0].text)))


def generate_page_copy(
    hypothesis: PullHypothesis,
    program: str,
    api_key: str,
) -> PageCopy:
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _PAGE_PROMPT.format(
        program=program or "Not provided.",
        project=hypothesis.project or "not specified",
        urgency=hypothesis.urgency or "not specified",
        look=hypothesis.look or "not specified",
        lacking=hypothesis.lacking or "not specified",
    )
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return PageCopy(**json.loads(_strip_fences(message.content[0].text)))


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()
