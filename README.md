# auto-bml

Automated, iterative build-measure-learn loops for startups

One mutable artifact (your landing page), one metric (ads traction), iterated by an agent

## How it works

Each iteration is a 6-hour window of live Google Ads data:

```
Using pull.csv + program.md, auto-bml:

    → reviews pull.csv hypotheses and picks a variable to test (see PULL variables below)
    → generates landing page, commits to docs/
    → serves landing page via GitHub Pages
    → generates ad copy
    → generates keywords
    → launches Google Ads campaign
        → waits [6 hours]
    → pulls Impressions, CTR, CVR from Google Ads
    → updates pull.csv, opens PR with results
    → reviews pull.csv hypotheses and picks a variable to test

```

## The PULL variables

| Variable | Question it answers |
|----------|---------------------|
| `project` | What specific job is the customer trying to complete? |
| `urgency` | Why can't they ignore this right now? |
| `look` | What solutions are they currently evaluating? |
| `lacking` | Where do those solutions fall short? |

`project`, `urgency`, and `look` are tested via ad copy. `lacking` is tested via the landing page.

---

## Quick start

### What you need before you begin

- A GitHub account
- A Google Ads account with existing spend (developer token issued same-day)
- A Google Cloud project with OAuth2 credentials — [create one here](https://console.cloud.google.com) in ~5 minutes: enable the Google Ads API, create an OAuth 2.0 Client ID (Desktop app type)
- An Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

---

### Step 1 — Create a GitHub repo

Create a new public GitHub repo. This is where your landing page and iteration history will live.

---

### Step 2 — Install auto-bml and create your .env

```bash
pip install auto-bml
```

In the root of your repo, create a `.env` file:

```bash
curl -o .env https://raw.githubusercontent.com/beakerstreet/auto-bml/main/.env.example
```

Fill in every field. Leave `GOOGLE_ADS_REFRESH_TOKEN` blank — onboarding fills it in automatically.

Add `.env` to your `.gitignore` if it isn't already.

---

### Step 3 — Run onboarding

```bash
cd your-repo
auto-bml onboard
```

This will:
1. Read your `.env`
2. Open a browser for Google OAuth2 (the only interactive step)
3. Validate your Google Ads connection
4. Push all credentials as GitHub Actions secrets to your repo
5. Enable GitHub Pages on the repo (served from `docs/`)
6. Create `pull.csv`, `program.md`, `.bml/runs.json`, and workflow files

---

### Step 4 — Fill in your context

**`program.md`** — describe what your product does in one paragraph. Do not describe the target customer; the PULL variables carry that signal.

**`pull.csv`** — fill in the first row with your best current hypotheses:

```
project:  the specific job your customer is trying to complete
urgency:  why they can't ignore it right now
look:     what solutions they're currently evaluating
lacking:  where those solutions fall short
```

---

### Step 5 — Launch

Commit and push. Then go to your repo on GitHub → Actions → BML Launch → Run workflow.

The first iteration starts immediately. Your landing page goes live at `https://your-username.github.io/your-repo`. Results arrive as a PR ~6 hours later.

---

## Cost per iteration

| Item | Cost |
|---|---|
| Google Ads | ~$5 (6hrs at $20/day default budget) |
| Claude API | ~$0.05 |
| GitHub Actions | ~2 CI minutes |
| Hosting | Free (GitHub Pages) |

---

## Repo structure after onboarding

```
your-repo/
├── .github/workflows/
│   ├── bml-launch.yml      ← trigger manually to start a run
│   └── bml-measure.yml     ← runs hourly, measures after 6h window
├── .bml/
│   └── runs.json           ← run state (committed automatically)
├── docs/
│   └── index.html          ← landing page (updated each iteration)
├── pull.csv                ← append-only iteration log
└── program.md              ← product description
```
