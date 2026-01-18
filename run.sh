#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Bybit Historical Data Downloader
# ------------------------------------------------------------
# NOTES:
# - Runs HEADLESS by default (no browser UI).
# - Fully automates Bybit UI clicks using Playwright.
# - Safe chunking: chunk-days MUST be < 6 (Bybit UI limitation).
# - Large date ranges will produce MANY files (especially L2Book).
# - If something breaks, try:
#     * reducing CHUNK_DAYS
#     * running with --no-headless via CLI for debugging
#
# You can override any variable below via environment variables:
#   SYMBOL=ETHUSDT DATASET=l2book ./run.sh
# ============================================================

# -----------------------
# Config (defaults)
# -----------------------
SYMBOL="${SYMBOL:-BTCUSDT}"
MARKET="${MARKET:-contract}"     # spot | contract
DATASET="${DATASET:-trades}"     # trades | l2book
START_DATE="${START_DATE:-2025-10-18}"
END_DATE="${END_DATE:-2026-01-18}"
CHUNK_DAYS="${CHUNK_DAYS:-5}"

# Output base directory
OUT_BASE="${OUT_BASE:-/home/pasha/projects/mlfindgen_lab/data}"
OUT_DIR="${OUT_BASE}/${DATASET}"

# -----------------------
# Environment
# -----------------------
# Ensure Python can find src/
export PYTHONPATH="${PYTHONPATH:-$(pwd)/src}"

# Create output directory if missing
mkdir -p "${OUT_DIR}"

# -----------------------
# Info
# -----------------------
echo "========================================"
echo "Bybit Historical Data Downloader"
echo "----------------------------------------"
echo "Symbol     : ${SYMBOL}"
echo "Market     : ${MARKET}"
echo "Dataset    : ${DATASET}"
echo "Date range : ${START_DATE} → ${END_DATE}"
echo "Chunk days : ${CHUNK_DAYS}"
echo "Output dir : ${OUT_DIR}"
echo "========================================"
echo

# -----------------------
# Run
# -----------------------
python -m src.main download "${MARKET}" "${DATASET}" \
  --symbol "${SYMBOL}" \
  --start "${START_DATE}" \
  --end "${END_DATE}" \
  --out "${OUT_DIR}" \
  --chunk-days "${CHUNK_DAYS}"

echo
echo "Done ✅"
