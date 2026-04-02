# auto-bml

Automated, iterative Build-Measure-Learn loops for landing pages, powered by Google Ads and Claude.

Modeled on [karpathy/autoresearch](https://github.com/karpathy/autoresearch): one mutable artifact (your landing page), one metric (PULL score), iterated by an agent until demand signal is maximised.

## How it works

Each iteration is a 6-hour window of live Google Ads data:

```
pull.csv + program.md
    → Claude generates landing page copy + ad copy + keywords
    → Landing page deployed via Vercel/Netlify webhook
    → Google Ads campaign launched
    → [6 hours]
    → CPC + conversion rate pulled from Google Ads
    → PULL score calculated (1–5 log scale)
    → Claude refines PULL hypotheses
    → pull.csv updated, PR opened with results
```

The PULL score is logarithmic: a 5 means customers are ripping the product off the shelf; a 1 means near-zero demand signal. Each step is ~10x more demand intensity than the previous.

## Setup

### Prerequisites

- Existing Google Ads account (with spend history — developer token is issued same-day)
- Google Cloud project with OAuth2 credentials ([5 min setup](https://console.cloud.google.com))
- Anthropic API key
- Vercel or Netlify deploy webhook URL
- Stripe payment link for your product

### 1. Install auto-bml

```bash
pip install auto-bml
```

### 2. Create your .env file

In the root of your landing page repo:

```bash
cp .env.example .env   # then fill in your credentials
```

All fields are documented inline in `.env.example`.

### 3. Run onboarding

```bash
cd your-landing-page-repo
auto-bml onboard
```

This will:
- Open a browser for Google OAuth2 (the only interactive step)
- Validate your Google Ads connection
- Push all credentials as GitHub Actions secrets
- Scaffold `pull.csv`, `program.md`, and workflow files into your repo

### 4. Wire your landing page to BML copy

Your page needs to read copy from environment variables at build time:

| Variable | Content |
|---|---|
| `BML_HEADLINE` | Main headline |
| `BML_SUBHEADLINE` | Subheadline |
| `BML_BODY` | Body copy |
| `BML_CTA` | CTA button text |
| `BML_CTA_URL` | Stripe payment link URL |

**Netlify**: auto-bml writes `bml_copy.json` to the repo before triggering your build hook — read from that file at build time instead.

### 5. Fill in your startup context

Edit `program.md` — describe your startup, target customer, and the problem you're solving.

Edit the first row of `pull.csv` with your best current hypotheses for all four variables.

### 6. Launch

Trigger `BML Launch` from GitHub Actions. Everything after that is automated.

## The PULL variables

| Variable | Question it answers |
|----------|---------------------|
| `project` | What specific job is the customer trying to complete? |
| `urgency` | Why can't they ignore this right now? |
| `look` | What solutions are they currently evaluating? |
| `lacking` | Where do those solutions fall short? |

## Cost

Each iteration costs approximately:
- Google Ads: `daily_budget_usd` (default $20, prorated to 6 hours ≈ $5)
- Claude API: ~$0.05 per launch + measure cycle
- GitHub Actions: ~2 minutes of CI time per hourly measure check

## File structure (in your repo)

```
your-landing-page-repo/
├── .github/workflows/
│   ├── bml-launch.yml      ← trigger manually to start a run
│   └── bml-measure.yml     ← runs hourly, collects data after 6h
├── .bml/
│   └── runs.json           ← run history (committed by the action)
├── pull.csv                ← PULL hypotheses (updated each iteration)
├── program.md              ← your startup context
└── bml_copy.json           ← latest generated copy (Netlify only)
```
