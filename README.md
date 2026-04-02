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

- Google Ads account ([create one](https://ads.google.com))
- Google Ads API developer token ([apply here](https://developers.google.com/google-ads/api/docs/first-call/dev-token)) — approval can take days
- Google Cloud project with Google Ads API enabled and OAuth2 credentials
- Anthropic API key
- Vercel or Netlify deploy webhook URL

> **Note on developer token approval**: Google requires approval for standard API access. Test account access is available immediately and sufficient for development.

### 1. Install auto-bml locally

```bash
pip install auto-bml
```

### 2. Run onboarding in your landing page repo

```bash
cd your-landing-page-repo
auto-bml onboard --repo your-org/your-repo
```

This will:
- Walk through Google Ads OAuth2 (opens browser)
- Push all credentials as GitHub Actions secrets
- Scaffold `pull.csv` and `program.md` into your repo

### 3. Add workflow files

Copy the workflow templates into your repo:

```bash
cp path/to/auto-bml/workflow-templates/*.yml .github/workflows/
```

### 4. Wire your landing page to BML copy

Your page needs to read copy from environment variables (Vercel) or `bml_copy.json` (Netlify):

**Vercel**: Read `process.env.BML_HEADLINE`, `BML_SUBHEADLINE`, `BML_BODY`, `BML_CTA` at build time.

**Netlify**: Read from `bml_copy.json` at build time (auto-bml writes this file before triggering your deploy hook).

### 5. Fill in your startup context

Edit `program.md` to describe your startup, target customer, and the problem you're solving.

Edit `pull.csv` with your best current hypotheses:

```csv
project,urgency,look,lacking
migrate postgres to cloud,upcoming AWS contract renewal,managed database comparison articles,no good cost calculator for our db size
```

### 6. Launch a BML run

Trigger the `BML Launch` workflow manually from GitHub Actions. It will:
1. Deploy your landing page with Claude-generated copy
2. Launch a Google Ads campaign
3. Return in 6 hours via the scheduled `BML Measure` workflow

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
