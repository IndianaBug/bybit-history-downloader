# src/main.py
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Literal

from src.client import BybitHistoryClient

Margin = Literal["Spot", "Contract"]
DataType = Literal["Trades", "L2Book"]


def _norm_margin(s: str) -> Margin:
    s = s.strip().lower()
    if s == "spot":
        return "Spot"
    if s in ("contract", "derivatives", "perp", "futures"):
        return "Contract"
    raise argparse.ArgumentTypeError("margin must be 'spot' or 'contract'")


def _norm_dtype(s: str) -> DataType:
    s = s.strip().lower()
    if s in ("trades", "trade"):
        return "Trades"
    if s in ("l2book", "l2", "orderbook", "order_book"):
        return "L2Book"
    raise argparse.ArgumentTypeError("data_type must be 'trades' or 'l2book'")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bybit-history",
        description="Bybit history-data downloader (Playwright).",
    )
    p.add_argument("--browser", default="firefox", help="firefox|chromium|webkit")
    p.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run browser headless (default: true). Use --no-headless to see UI.",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    # ---- symbols ----
    ps = sub.add_parser("symbols", help="List available symbols.")
    ps.add_argument("margin", type=_norm_margin, help="spot|contract")

    # ---- download ----
    pd = sub.add_parser("download", help="Download data.")
    pd.add_argument("margin", type=_norm_margin, help="spot|contract")
    pd.add_argument("data_type", type=_norm_dtype, help="trades|l2book")
    pd.add_argument("--symbol", required=True, help="e.g. BTCUSDT")
    pd.add_argument("--start", required=True, help="YYYY-MM-DD")
    pd.add_argument("--end", required=True, help="YYYY-MM-DD")
    pd.add_argument("--out", required=True, help="Output directory")
    pd.add_argument(
        "--chunk-days",
        type=int,
        default=5,
        help="Chunk size in days (must be < 6)",
    )

    return p


async def _run_symbols(args) -> int:
    async with BybitHistoryClient(
        headless=args.headless, browser_name=args.browser
    ) as c:
        if args.margin == "Spot":
            await c.show_spot_symbols()
        else:
            await c.show_contract_symbols()
    return 0


async def _run_download(args, parser: argparse.ArgumentParser) -> int:
    if args.chunk_days >= 6:
        parser.error("chunk-days must be < 6")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    async with BybitHistoryClient(
        headless=args.headless, browser_name=args.browser
    ) as c:
        await c.download_data(
            margin=args.margin,
            data_type=args.data_type,
            symbol=args.symbol,
            start_date=args.start,
            end_date=args.end,
            final_path=str(out_dir),
            chunk_days=args.chunk_days,
        )
    return 0


async def amain(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "symbols":
        return await _run_symbols(args)
    if args.cmd == "download":
        return await _run_download(args, parser)

    parser.error("unknown command")
    return 2


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(amain(argv)))


if __name__ == "__main__":
    main()
