# 📊 Bybit Historical Data Puller (Playwright)

Bybit provides **high-quality historical market data**, including:
- Full trade history  
- Deep L2 order books  
- Spot & derivatives markets  

The downside is that **downloading this data manually is painful** — lots of UI clicks, symbol/date selection, and repeating the same workflow over and over.

---

## 💡 What this project does

This tool **automates the entire Bybit download flow** using Playwright:
- handles all UI interaction for you
- selects symbols and date ranges
- downloads and saves data locally

The goal is to make historical data collection **fast, repeatable, and hands-off**.

---

## ⚠️ Project status

🚧 **Fresh release — expect rough edges**

Bybit UI changes and browser automation can be flaky.
If something breaks:
- try running with `--no-headless` to see the browser
- reduce `--chunk-days` if downloads fail

Bug reports and PRs are welcome.

---

## 🚀 Quick Start (Linux / WSL)

⚠️ Not for native Windows.  
Use **WSL (Ubuntu)** or a Linux machine.

From the project root, run:

    chmod +x setup.sh
    ./setup.sh
    source .venv/bin/activate
    export PYTHONPATH=$PWD/src

That’s it — **no manual downloads, cookies, or browser setup required**.

---

## 🖥️ CLI Usage

Entry point:  
`src/main.py`

General syntax:

    python -m src.main [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]

### Global options

| Flag | Description |
|------|------------|
| `--browser` | firefox (default), chromium, webkit |
| `--headless / --no-headless` | Run browser headless (default: headless) |

---

## ✅ What you can do

### 1) List spot symbols

    python -m src.main symbols spot

### 2) List contract symbols

    python -m src.main symbols contract

### 3) Download historical data

**Spot trades example**

    python -m src.main download spot trades \
      --symbol BTCUSDT \
      --start 2026-01-01 \
      --end 2026-01-03 \
      --out ./data \
      --chunk-days 5

**Contract L2 order book example**

    python -m src.main download contract l2book \
      --symbol BTCUSDT \
      --start 2026-01-01 \
      --end 2026-01-03 \
      --out ./data \
      --chunk-days 5

### Supported datasets
- trades  
- l2book  

---

## ⚠️ Chunking rule (important)

    chunk-days MUST be < 6

This is a **Bybit UI limitation**.  
The CLI will error if you exceed it.

---

## 🧠 Python API (library usage)

You can also use this directly in Python:

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

---

## ⚠️ Disclaimer

This tool automates Bybit’s **public web UI**.  
Use responsibly and **at your own risk**.
