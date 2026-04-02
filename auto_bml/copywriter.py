import json

import anthropic

from .models import PageCopy, PullHypothesis

_SYSTEM = """You are a direct-response copywriter who understands the PULL framework.
PULL means customers are already trying to solve a specific problem — your job is to
reflect their existing demand back at them, not to manufacture desire.

Your copy must pass this test: a customer with genuine demand should feel
"this was written for me." A customer without demand should feel nothing."""

_PROMPT = """Startup context:
{program}

Current PULL hypothesis:
- Project (job they're trying to do): {project}
- Urgency (why they can't ignore it): {urgency}
- Look (what they're trying now): {look}
- Lacking (how current solutions fall short): {lacking}

Write landing page copy and Google Ads copy that reflects this exact demand.

Return ONLY valid JSON matching this structure:
{{
  "headline": "...",
  "subheadline": "...",
  "body": "2-3 sentences max",
  "cta": "...",
  "ad_headlines": ["...", "...", "..."],
  "ad_descriptions": ["...", "..."],
  "keywords": ["keyword 1", "keyword 2", "...up to 20 keywords"]
}}

Constraints:
- ad_headlines: max 30 characters each
- ad_descriptions: max 90 characters each
- keywords: phrase or broad match, directly derived from the project + look variables
- Do not invent benefits not implied by the hypothesis
"""


def generate(hypothesis: PullHypothesis, program: str, api_key: str) -> PageCopy:
    client = anthropic.Anthropic(api_key=api_key)

    prompt = _PROMPT.format(
        program=program or "Not provided.",
        project=hypothesis.project or "Not specified.",
        urgency=hypothesis.urgency or "Not specified.",
        look=hypothesis.look or "Not specified.",
        lacking=hypothesis.lacking or "Not specified.",
    )

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)
    return PageCopy(**data)
