# Prosperity Visualizer

A static, client-side dashboard for replaying and analysing [IMC Prosperity](https://prosperity.imc.com/) backtest logs. No server required — drag-and-drop a log file and explore tick-level L2 order book data in your browser.

**[Live demo →](https://prosperity-visualizer.vercel.app)**

---

## Features

| Tab | What it shows |
|-----|--------------|
| **Time-Series** | Mid price + own trade markers (coloured by counterparty), submitted order overlays, PnL curve, bid-ask spread, tick-level order book snapshot, execution table, market pressure gauge |
| **Volume Profile** | Price-volume histogram of your own fills |

Additional capabilities:

- **Tick-level playback** — scrub through every engine iteration; ◀ ▶ step controls or space/arrow keyboard shortcuts
- **Multi-run comparison** — upload multiple `.log` files and overlay PnL curves
- **L2 order book replay** — live 3-level depth display updates with the playback position
- **Submitted vs filled orders** — see which orders were placed and which were matched
- **Counterparty breakdown** — PnL attributed per named counterparty

---

## Quick Start

Open `index.html` directly in any modern browser (Chrome, Firefox, Edge, Safari):

```bash
# Option A — open directly
open index.html          # macOS
start index.html         # Windows

# Option B — local dev server (avoids ES module CORS in some browsers)
python -m http.server 8000
# then open http://localhost:8000
```

Drag `sample/demo.log` onto the page (or click **Upload New Logs**).

---

## Log Format

The visualizer parses three formats:

### 1. Backtest `.log` (from `backtester/`)

```
Sandbox logs:
{"lambdaLog":"[<compressed_state>,<orders>,0,\"\",\"<logs>\"]"}
...

Activities log:
day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;mid_price;profit_and_loss
0;0;EMERALDS;10002;1;...;10003.0;0.0
...

Trade History:
[{"timestamp":100,"symbol":"EMERALDS","price":10000,"quantity":3,"buyer":"SUBMISSION","seller":""}]
```

### 2. Submission `.json` (downloaded from the competition portal)

```json
{
  "activitiesLog": "day;timestamp;...\n0;0;EMERALDS;...",
  "logs": [{"lambdaLog": "[...]"}, ...],
  "tradeHistory": [...]
}
```

### 3. `.zip` archive (competition download)

The visualizer auto-extracts the first `.log` or `.json` file from the archive.

### Lambda log format

The `lambdaLog` string is a JSON array produced by the `Logger` class in `example_trader.py`:

```
[
  [timestamp, traderData, listings, orderDepths, ownTrades, marketTrades, position, observations],
  [[symbol, price, qty], ...],  // submitted orders
  conversions,
  traderData,
  "log lines..."
]
```

The `orderDepths` entry is `{symbol: [buyOrders, sellOrders]}` where `buyOrders` is `{price: volume, ...}` with positive volumes and `sellOrders` has negative volumes (Prosperity convention).

---

## Running a Backtest Locally

The `backtester/` directory contains a local fork of [jmerle's backtester](https://github.com/jmerle/imc-prosperity-3-backtester), adapted for Prosperity data.

```bash
pip install -e backtester/

# Backtest your trader against the tutorial round
prosperity4bt example_trader.py 0

# Save output for the visualizer
prosperity4bt example_trader.py 0 --out my_run.log
```

Then drag `my_run.log` into the visualizer.

---

## Deploy to Vercel

```bash
npm i -g vercel
vercel deploy --prod
```

`vercel.json` is already configured for static hosting. No build step needed.

---

## Architecture

```
index.html          Loads Plotly.js + JSZip from CDN; imports ES modules
src/
  parser.js         Client-side log parsing (ports Python dashboard.py parsing logic)
                    parseFile() → per-symbol data structure
                    parseBT()   → backtest .log format
                    parseJSON() → submission .json format
  charts.js         Plotly.js chart renderers (t0, t3) and sidebar helpers
  app.js            State management, file upload, playback, tab routing
sample/
  demo.log          Tutorial-round data (2 products, 300 ticks each)
backtester/         Local backtester fork
datamodel.py        Official Prosperity 4 data classes (reference)
example_trader.py   Minimal trader with Logger class
```

All parsing happens in the browser — no data is sent to any server.

---

## Extending

**Add a new tab:** define a `tN()` function in `charts.js`, add an entry to `TABS` in `app.js`, and route it in `rTab()`.

**Add custom signals to your trader:** the parser preserves all fields in the data structure; extend `t0()` in `charts.js` to visualise them.

**Log format:** the `Logger` class in `example_trader.py` produces all output needed by the visualizer. Copy it verbatim into your trader.

---

## Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| [Plotly.js](https://plotly.com/javascript/) | 2.35.2 | Interactive charts (CDN) |
| [JSZip](https://stuk.github.io/jszip/) | 3.10.1 | ZIP extraction (CDN) |

Python backtester dependencies: `numpy` (data loading only).

---

## License

MIT
