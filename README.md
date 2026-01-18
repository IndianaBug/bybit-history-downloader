# 📊 Bybit Historical Data Puller (Playwright)

Bybit is awesome — they provide **high-quality historical market data**, including:
- **Full trade history**
- **Deep L2 order books**
- **Spot & contract markets**

The only downside is that **downloading it manually is annoying**: lots of UI clicks, symbol/date selection, and repeating the same workflow over and over.

### 💡 This project is the solution
This tool **automates the entire Bybit download flow** (all the clicks) and saves the data locally in minutes — **no manual interaction**.

### ⚠️ Project status
🚧 **Just released — expect bugs**  
Bybit UI changes + Playwright timing can be flaky. If something breaks, try `--no-headless` to see what the UI is doing and/or reduce `--chunk-days`.

---

## 🚀 Quick Start (WSL / Linux)

> Not for native Windows. Use **WSL (Ubuntu)** or Linux.

From the project root:

    chmod +x setup.sh
    ./setup.sh
    source .venv/bin/activate
    export PYTHONPATH=$PWD/src

That’s it — you **don’t need to download anything else** manually.

---

## 🖥️ CLI Usage

Entry point: `src/main.py`

    python -m src.main [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]

### Global Options
| Flag | Description |
|-----|------------|
| `--browser` | `firefox` (default), `chromium`, `webkit` |
| `--headless / --no-headless` | Run browser headless (default: **headless**) |

---

## ✅ 3 Things You Can Do

### 1) List spot symbols
    python -m src.main symbols spot

### 2) List contract symbols
    python -m src.main symbols contract

### 3) Download data (spot or contract)
**Spot trades example:**
    python -m src.main download spot trades \
      --symbol BTCUSDT \
      --start 2026-01-01 \
      --end 2026-01-03 \
      --out ./data \
      --chunk-days 5

**Contract L2Book example:**
    python -m src.main download contract l2book \
      --symbol BTCUSDT \
      --start 2026-01-01 \
      --end 2026-01-03 \
      --out ./data \
      --chunk-days 5

Supported datasets:
- `trades`
- `l2book`

---

## ⚠️ Chunking Rule (Important)

    chunk-days MUST be < 6

This is a **Bybit UI limitation**. The CLI errors if you exceed it.

---

## 🧠 Python API (Direct Usage)

If you prefer using it as a library:

```python
from src.client import BybitHistoryClient
import asyncio

async def run():
    async with BybitHistoryClient() as c:
        await c.download_data(
            margin="Spot",
            data_type="Trades",
            symbol="BTCUSDT",
            start_date="2026-01-01",
            end_date="2026-01-03",
            final_path="./data",
            chunk_days=5,
        )

asyncio.run(run())


⚠️ Disclaimer

This tool scrapes Bybit’s public UI.
Use responsibly and at your own risk.
