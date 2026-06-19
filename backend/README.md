# DesktopClaw Backend

## Deep Web Research (`deep_web_search` tool)

The main agent uses a single tool **`deep_web_search`** for all web research. It does **not** expose `web_search` or `web_fetch` directly.

The pipeline:

1. **Iterative search** — multiple Bing queries (Playwright), updating knowledge each round
2. **Deep reading** — fetches and summarizes 10–20 pages (configurable)
3. **Cross-verification** — merges claims across sources; marks corroborated / single-source / disputed
4. **Structured report** — returns a layered Markdown report to the main agent

Typical runtime: **1–2 minutes**.

### Install

```bash
cd backend
pip install -e ".[web-search]"
playwright install chromium
```

### Configuration

```json
{
  "tools": {
    "web": {
      "proxy": null,
      "search": {
        "baseUrl": "https://cn.bing.com/search",
        "headless": true,
        "timeoutS": 30,
        "minIntervalS": 3.0,
        "maxRetries": 1
      },
      "research": {
        "maxPages": 15,
        "maxRounds": 5,
        "pagesPerRound": 3,
        "serpPerRound": 5,
        "fetchMaxChars": 8000,
        "fetchConcurrency": 3,
        "pageTimeoutS": 20,
        "totalTimeoutS": 120,
        "minConfidenceToStop": "medium"
      }
    }
  }
}
```

| `research` field | Default | Description |
|------------------|---------|-------------|
| `maxPages` | `15` | Total pages to read deeply (10–20 recommended) |
| `maxRounds` | `5` | Max search iterations |
| `pagesPerRound` | `3` | Pages to deep-read per round |
| `serpPerRound` | `5` | Bing results per search |
| `fetchMaxChars` | `8000` | Max chars per page fetch |
| `fetchConcurrency` | `3` | Parallel page reads |
| `pageTimeoutS` | `20` | Per-page timeout |
| `totalTimeoutS` | `120` | Whole research timeout |
| `minConfidenceToStop` | `medium` | Stop when confidence reaches this and no open questions |

Bing Playwright settings remain under `tools.web.search` (see `baseUrl`, `minIntervalS`, etc.).

### Compliance notice

Automated Bing access may violate Microsoft's terms of service. Deep research increases request volume. Use at your own risk.

### Troubleshooting

- **Playwright not installed**: `pip install "desktopclaw[web-search]"` and `playwright install chromium`
- **Research timeout**: increase `totalTimeoutS` or reduce `maxPages`
- **Captcha**: increase `minIntervalS`, use `proxy`, reduce `maxRounds`
