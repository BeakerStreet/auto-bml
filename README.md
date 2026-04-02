# auto-bml

Automated, iterative Build-Measure-Learn loops for landing pages, powered by Google Ads and Claude.

Modeled on [karpathy/autoresearch](https://github.com/karpathy/autoresearch): one mutable artifact (your landing page), one metric (customer buys), iterated by an agent until demand signal is maximised.

## How it works

Each iteration is a 6-hour window of live Google Ads data:

```
pull.csv + program.md
    → Claude generates landing page copy + ad copy + keywords
    → Landing page deployed via Vercel/Netlify webhook
    → Google Ads campaign launched
    → [6 hours]
    → Impressions, CTR, CVR pulled from Google Ads
    → Claude refines PULL hypotheses and picks next variable to test
    → pull.csv updated, PR opened with results
```

## The PULL variables

| Variable | Question it answers |
|----------|---------------------|
| `project` | What specific job is the customer trying to complete? |
| `urgency` | Why can't they ignore this right now? |
| `look` | What solutions are they currently evaluating? |
| `lacking` | Where do those solutions fall short? |

`project`, `urgency`, and `look` are tested via ad copy. `lacking` is tested via the landing page. The customer does not need to be defined — whoever clicks an ad written from these four variables is, by definition, the customer.

---

## Quick start

### What you need before you begin

- A GitHub account
- A Google Ads account with existing spend (developer token issued same-day)
- A Google Cloud project with OAuth2 credentials — [create one here](https://console.cloud.google.com) in ~5 minutes: enable the Google Ads API, create an OAuth 2.0 Client ID (Desktop app type)
- An Anthropic API key — [console.anthropic.com](https://console.anthropic.com)
- A Stripe payment link — [dashboard.stripe.com → Payment Links](https://dashboard.stripe.com/payment-links)

---

### Step 1 — Create a landing page repo

Create a new GitHub repo. It needs one deployable page that reads the following environment variables at build time:

| Variable | Content |
|---|---|
| `BML_HEADLINE` | Main headline |
| `BML_SUBHEADLINE` | Subheadline |
| `BML_BODY` | Body copy |
| `BML_CTA` | CTA button text |
| `BML_CTA_URL` | Stripe payment link URL |

Any JS framework works (Next.js, Astro, plain HTML). The page just needs to render these values.

---

### Step 2 — Deploy to Vercel or Netlify

Connect your repo to [Vercel](https://vercel.com) or [Netlify](https://netlify.com).

You'll get a free subdomain automatically — `your-project.vercel.app` or `your-project.netlify.app`. This is your landing page URL and your Google Ads destination URL. No custom domain needed to start.

Then create a deploy hook:
- **Vercel**: Project Settings → Git → Deploy Hooks → Create hook
- **Netlify**: Site Configuration → Build & Deploy → Build hooks → Add build hook

Copy the webhook URL — you'll need it in the next step.

---

### Step 3 — Install auto-bml and create your .env

```bash
pip install auto-bml
```

In the root of your landing page repo, create a `.env` file. Copy the template:

```bash
curl -o .env https://raw.githubusercontent.com/beakerstreet/auto-bml/main/.env.example
```

Fill in every field. All fields are documented inline. Leave `GOOGLE_ADS_REFRESH_TOKEN` blank — onboarding fills it in automatically.

Add `.env` to your `.gitignore` if it isn't already.

---

### Step 4 — Run onboarding

```bash
cd your-landing-page-repo
auto-bml onboard
```

This will:
1. Read your `.env`
2. Open a browser for Google OAuth2 (the only interactive step)
3. Validate your Google Ads connection
4. Push all credentials as GitHub Actions secrets to your repo
5. Create `pull.csv`, `program.md`, `.bml/runs.json`, and workflow files

---

### Step 5 — Fill in your context

**`program.md`** — describe what your product does in one paragraph. Do not describe the target customer; the PULL variables carry that signal.

**`pull.csv`** — fill in the first row with your best current hypotheses:

```
project:  the specific job your customer is trying to complete
urgency:  why they can't ignore it right now
look:     what solutions they're currently evaluating
lacking:  where those solutions fall short
```

---

### Step 6 — Launch

Commit and push. Then go to your repo on GitHub → Actions → BML Launch → Run workflow.

The first iteration starts immediately. Results arrive as a PR ~6 hours later.

---

## Cost per iteration

| Item | Cost |
|---|---|
| Google Ads | ~$5 (6hrs at $20/day default budget) |
| Claude API | ~$0.05 |
| GitHub Actions | ~2 CI minutes |

---

## Repo structure after onboarding

```
your-landing-page-repo/
├── .github/workflows/
│   ├── bml-launch.yml      ← trigger manually to start a run
│   └── bml-measure.yml     ← runs hourly, measures after 6h window
├── .bml/
│   └── runs.json           ← run state (committed automatically)
├── pull.csv                ← append-only iteration log
├── program.md              ← product description + Stripe link
└── bml_copy.json           ← latest copy snapshot (Netlify only)
```
