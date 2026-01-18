# src/get_symbols.py

import asyncio
import zipfile
from pathlib import Path
from typing import List, Literal, Set

import pytest
from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright, expect
from tqdm import tqdm

from utils import gunzip_file, split_date_range

from .reporters import DownloadTqdm


class BybitHistoryClient:
    """
    Base class for BybitHistoryClient
    """

    def __init__(self, headless: bool = True, browser_name: str = "firefox"):
        self.BASE_HISTORY_URL = "https://www.bybit.com/derivatives/en/history-data"
        self.headless = headless
        self.browser_name = browser_name
        self._pw = None
        self._browser = None
        self._context = None
        self.page: Page | None = None

    async def __aenter__(self):
        self._pw = await async_playwright().start()
        browser_type = getattr(self._pw, self.browser_name)
        self._browser = await browser_type.launch(headless=self.headless)
        self._context = await self._browser.new_context(accept_downloads=True)
        self.page = await self._context.new_page()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # close in reverse order
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def show_spot_symbols(self):
        """Display available SPOT symbols"""
        symbols = await self._get_symbols("Spot")
        self._print_symbols("SPOT", symbols)

    async def show_contract_symbols(self):
        """Display available CONTRACT symbols"""
        symbols = await self._get_symbols("Contract")
        self._print_symbols("CONTRACT", symbols)

    async def download_data(
        self,
        margin: Literal["Spot", "Contract"],
        data_type: Literal["Trades", "L2Book"],
        symbol: str,
        start_date: str,
        end_date: str,
        final_path: str,
        *,
        chunk_days: int = 7,
    ):
        """
        Split [start_date, end_date] into chunks of chunk_days and call _download_data for each chunk.
        Shows a tqdm progress bar over chunks.
        """
        ranges = split_date_range(start_date, end_date, chunk_days)

        for s, e in tqdm(
            ranges,
            desc=f"{margin}-{data_type}-{symbol}",
            unit="chunk",
            dynamic_ncols=True,
        ):
            await self._download_data_helper(
                margin=margin,
                data_type=data_type,
                symbol=symbol,
                start_date=s,
                end_date=e,
                final_path=final_path,
            )

    async def _download_data_helper(
        self,
        margin: Literal["Spot", "Contract"],
        data_type: Literal["Trades", "L2Book"],
        symbol: str,
        start_date: str,
        end_date: str,
        final_path: str,
    ):
        """Get a list of available spot contract symbols"""
        page = await self._walk_over_site(
            margin=margin,
            data_type=data_type,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
        page, message = await self._date_helper(page, start_date, end_date)
        if message == "found symbols downloading":
            print(f"Downloading {margin}-{data_type}-{symbol} to {final_path}")
            await self._click_and_save_download(
                page=page,
                save_dir=final_path,
                click_locator="Download",
            )
        else:
            print(
                f"Data not found for {margin}-{data_type}-{symbol} date range: {
                    start_date
                } to {end_date}. "
            )
            page.close()

    async def _walk_over_site(
        self,
        margin: Literal["Spot", "Contract"],
        data_type: Literal["Trades", "L2Book"],
        symbol: str,
        start_date: str,
        end_date: str,
    ):
        if self.page is None:
            raise RuntimeError(
                "Client not started. Use: async with BybitHistoryClient(...) as c:"
            )
        page = self.page
        await page.goto(
            self.BASE_HISTORY_URL,
            timeout=100_000,
            wait_until="domcontentloaded",
        )
        await page.wait_for_load_state("networkidle", timeout=60_000)
        hover_element = (
            "Public Trading History" if data_type == "Trades" else "OrderBook"
        )
        # SPOT/CONTRACT button
        await self._hover(page, element=hover_element)
        await self._attepth_click_visible_element(
            page=page,
            margin=margin,
            nth=self._get_nth(margin=margin, data_type=data_type),
        )
        # symbol selector
        await self._antd_select_option(
            page,
            select_click=page.locator(".ant-select-selection-overflow"),
            symbol=symbol,
            search_input=page.locator("#rc_select_0"),
        )

        # await page.locator(".ant-select-selection-overflow").click()
        # cycle selector
        select_cycle = page.locator(".ant-select-selector > .ant-select-selection-item")
        await select_cycle.click()
        dropdown_cycle = page.locator(".ant-select-dropdown:visible")
        await dropdown_cycle.get_by_text("Everyday", exact=True).click()
        return page

    async def _date_helper(self, page, start_date, end_date):
        start = page.get_by_role("textbox", name="Start date")
        end = page.get_by_role("textbox", name="End date")

        await start.click()
        await start.fill(start_date)
        await start.press("Enter")

        await end.click()
        await end.fill(end_date)
        await end.press("Enter")

        await page.get_by_text("Confirm").click()

        # Wait a bit for the list to render (replace your sleep with deterministic wait)
        # We try to detect "Detail" rows appearing.
        detail = page.get_by_text("Detail", exact=True)

        try:
            await detail.first.wait_for(state="visible", timeout=4000)
            return page, "found symbols downloading"
        except PlaywrightTimeoutError:
            return page, f"No data for this date range ({start_date} to {end_date})"

    @classmethod
    async def _click_and_save_download(
        cls,
        page,
        save_dir,
        click_locator="Download",
        prefix: str = "",
        *,
        # how long to keep collecting extra downloads after the click
        collect_window_ms: int = 1200,
        poll_ms: int = 100,  # polling frequency for download collection
    ):
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        btn = page.get_by_text(click_locator, exact=True)
        await btn.wait_for(state="visible")
        await btn.scroll_into_view_if_needed()

        # ---- Collect 1..N downloads triggered by the click ----
        downloads = []

        def _on_download(d):
            downloads.append(d)

        page.on("download", _on_download)

        try:
            # Ensure at least one download happens (or we fail fast)
            async with page.expect_download(timeout=30_000):
                await btn.click()

            # Now collect any additional downloads that arrive shortly after
            idle_ms = 0
            last_count = len(downloads)
            max_wait_ms = collect_window_ms

            waited = 0
            while waited < max_wait_ms:
                await asyncio.sleep(poll_ms / 1000)
                waited += poll_ms

                if len(downloads) != last_count:
                    last_count = len(downloads)
                    idle_ms = 0
                else:
                    idle_ms += poll_ms
                    if idle_ms >= collect_window_ms:
                        break

        finally:
            page.remove_listener("download", _on_download)

        # Fallback: if for some reason downloads list is empty, nothing to save
        if not downloads:
            return []

        out_paths: list[Path] = []

        for i, download in enumerate(downloads, start=1):
            suggested = download.suggested_filename or f"download_{i}.bin"

            # apply prefix once per file; keep unique if multiple
            filename = f"{prefix}_{suggested}" if prefix else suggested

            out_path = save_dir / filename

            bar = DownloadTqdm(desc=out_path.name)
            await bar.start(download)
            try:
                await download.save_as(str(out_path))
            finally:
                await bar.stop(final_path=out_path)

            produced: list[Path] = [out_path]

            # ---- Post-processing: unzip/ungzip automatically ----
            # 1) If it's a ZIP, extract it (and delete zip), then gunzip any .gz inside
            if out_path.suffix.lower() == ".zip":
                extracted = []
                with zipfile.ZipFile(out_path, "r") as z:
                    for name in z.namelist():
                        z.extract(name, path=save_dir)
                        extracted.append(save_dir / name)
                out_path.unlink(missing_ok=True)

                # gunzip any .gz extracted
                final_extracted: list[Path] = []
                for p in extracted:
                    if p.suffix.lower() == ".gz":
                        final_extracted.append(gunzip_file(p, delete_original=True))
                    else:
                        final_extracted.append(p)

                produced = final_extracted

            # 2) If it's a .gz (csv.gz), gunzip and delete .gz
            elif out_path.suffix.lower() == ".gz":
                produced = [gunzip_file(out_path, delete_original=True)]

            out_paths.extend(produced)

        return out_paths

    def _get_nth(
        self,
        margin: Literal["Spot", "Contract"],
        data_type: Literal["Trades", "L2Book"],
    ):
        element_1 = "Public Trading History" if data_type == "Trades" else "OrderBook"
        if margin == "Contract" and element_1 == "Public Trading History":
            return 1
        if margin == "Spot" and element_1 == "Public Trading History":
            return 3
        if margin == "Contract" and element_1 == "OrderBook":
            return 4
        if margin == "Spot" and element_1 == "OrderBook":
            return 4

    async def _get_symbols(self, _type: Literal["Contract", "Spot"]) -> List[str]:
        if self.page is None:
            raise RuntimeError(
                "Client not started. Use: async with BybitHistoryClient(...) as c:"
            )

        page = self.page
        await page.goto(
            self.BASE_HISTORY_URL,
            timeout=100_000,
            wait_until="domcontentloaded",
        )
        await page.wait_for_load_state("networkidle", timeout=60_000)
        await self._hover(page, element="Public Trading History")
        await self._click_first_visible_contract(page)
        select_root = page.locator(".ant-select").first
        await expect(select_root).to_be_visible(timeout=30_000)
        await select_root.click()
        options = page.locator(
            ".ant-select-dropdown:visible .ant-select-item-option-content"
        )
        await expect(options.first).to_be_visible(timeout=30_000)
        dropdown = page.locator(".ant-select-dropdown:visible").first
        await dropdown.hover()
        symbols = await self._collect_ant_select_options(page=page, dropdown=dropdown)
        return symbols

    @classmethod
    async def _hover(
        cls,
        page,
        element: str = "Public Trading History",
    ):
        el = page.get_by_text(element, exact=True)
        box = await el.bounding_box()
        if box:
            await page.mouse.move(
                box["x"] + box["width"] * 0.5,
                box["y"] + box["height"] * 0.5,
            )
        await page.wait_for_timeout(400)

    @classmethod
    async def _attepth_click_visible_element(
        cls,
        page,
        nth,
        *,
        max_attempts: int = 20,
        delay_ms: int = 3000,
        margin: Literal["Spot", "Contract"],
    ):
        for attempt in range(1, max_attempts + 1):
            b = page.get_by_text(margin).nth(nth)
            try:
                if not await b.is_visible():
                    continue

                await b.click(timeout=2_00)
                return  # ✅ success

            except Exception:
                print(f"[attempt {attempt}] click failed on #{nth}, retrying scan...")
            await page.wait_for_timeout(delay_ms)
        raise RuntimeError("Failed to click a visible Contract button after retries")

    @classmethod
    async def _click_first_visible_contract(
        cls,
        page,
        *,
        max_attempts: int = 20,
        delay_ms: int = 3000,
    ):
        for attempt in range(1, max_attempts + 1):
            buttons = page.locator(".history-data__item-btn", has_text="Contract")
            count = await buttons.count()

            for i in range(count):
                b = buttons.nth(i)
                try:
                    if not await b.is_visible():
                        continue

                    await b.click(timeout=2_00)
                    return  # ✅ success

                except Exception:
                    print(f"[attempt {attempt}] click failed on #{i}, retrying scan...")

            # No successful click this round → wait and rescan
            await page.wait_for_timeout(delay_ms)

        raise RuntimeError("Failed to click a visible Contract button after retries")

    @classmethod
    async def _collect_ant_select_options(
        cls,
        *,
        page: Page,
        dropdown: Locator,
        option_selector: str = ".ant-select-item-option-content",
        max_iters: int = 2000,
        idle_iters: int = 2000,
        scroll_pause_ms: int = 10,
    ) -> List[str]:
        """
        Collects all option texts from an Ant Design Select dropdown
        using robust virtual-list scrolling.

        Returns a sorted list of unique option texts.
        """
        # Find the actual scroll container
        scroll_box = dropdown.locator(".rc-virtual-list-holder").first
        if await scroll_box.count() == 0:
            scroll_box = dropdown

        seen: Set[str] = set()
        no_progress = 0

        for _ in range(max_iters):
            # Collect visible options
            texts = await dropdown.locator(option_selector).all_text_contents()
            before_len = len(seen)

            for t in texts:
                t = t.strip()
                if t:
                    seen.add(t)

            # Read scroll state before scroll
            before_top, scroll_height, client_height = await scroll_box.evaluate(
                "(el) => [el.scrollTop, el.scrollHeight, el.clientHeight]"
            )

            # Scroll down
            await scroll_box.evaluate(
                "(el) => { el.scrollTop = el.scrollTop + el.clientHeight * 0.9; }"
            )

            # Allow virtual list to recycle DOM nodes
            await page.wait_for_timeout(scroll_pause_ms)

            # Read scroll state after scroll
            after_top, _, _ = await scroll_box.evaluate(
                "(el) => [el.scrollTop, el.scrollHeight, el.clientHeight]"
            )

            # Progress detection
            added_any = len(seen) > before_len
            scrolled_any = after_top > before_top
            at_bottom = after_top >= (scroll_height - client_height - 2)

            if not added_any and not scrolled_any:
                no_progress += 1
            else:
                no_progress = 0

            if at_bottom:
                break

            if no_progress >= idle_iters:
                break

        return sorted(seen)

    async def _antd_select_option(
        self,
        page,
        *,
        select_click,  # locator that opens the select
        symbol: str,  # exact symbol you want (e.g. BTCUSDT or BTCUSDT-342)
        search_input,  # locator for the rc_select input
        max_tries: int = 5,
    ):
        selector = page.locator(".ant-select-selection-overflow")
        await selector.wait_for(state="visible", timeout=30_000)
        await selector.click()

        await page.locator("#rc_select_0").fill(symbol)
        # n-------------
        ok = await self._select_virtual_option(page, symbol)
        selector = page.get_by_text(symbol)
        await selector.wait_for(state="visible", timeout=30_000)
        await selector.click()
        return page

    async def _select_virtual_option(self, page, text: str, max_tries: int = 80):
        import re

        dropdown = page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden)")
        await dropdown.wait_for(state="visible")

        holder = dropdown.locator(".rc-virtual-list-holder")
        await holder.wait_for(state="visible")

        # Match EXACT text (avoid BTCUSDT matching BTCUSDT-PERP, 1000BTCUSDT, etc.)
        exact = re.compile(rf"^{re.escape(text)}$")

        content = dropdown.locator(
            ".ant-select-item-option-content",
            has_text=exact,
        )

        # In some AntD versions the clickable target is the option wrapper
        option_wrapper = content.locator(
            "xpath=ancestor::*[contains(@class,'ant-select-item-option')]"
        )

        last_scroll_top = None

        for _ in range(max_tries):
            # If the row is mounted, it will become visible
            if await content.first.is_visible():
                await option_wrapper.first.scroll_into_view_if_needed()
                await option_wrapper.first.click()
                return True

            # scroll the holder a bit (virtual list)
            scroll_top = await holder.evaluate("el => el.scrollTop")
            if last_scroll_top is not None and abs(scroll_top - last_scroll_top) < 1:
                # no more scrolling possible (hit end)
                return False
            last_scroll_top = scroll_top

            await holder.evaluate("el => { el.scrollTop += 60; }")
            await page.wait_for_timeout(40)

        return False

    def _print_symbols(self, label: str, symbols: list[str]):
        print(f"\n=== {label} SYMBOLS ({len(symbols)}) ===")
        for s in sorted(symbols):
            print(s)
        print(f"=== END {label} SYMBOLS ===\n")

    async def _dump_all_dropdown_options(self, page):
        dropdown = page.locator(".ant-select-dropdown:visible")
        await dropdown.wait_for(state="visible", timeout=5000)

        scroller = dropdown.locator(".rc-virtual-list-holder")
        if await scroller.count() == 0:
            scroller = dropdown  # fallback if virtual holder not present

        options = dropdown.locator(".ant-select-item-option")
        await options.first.wait_for(state="visible", timeout=20000)

        seen = []
        seen_set = set()
        last_scroll_top = -1

        for _ in range(200):  # safety cap
            texts = [t.strip() for t in await options.all_inner_texts()]
            for t in texts:
                if t and t not in seen_set:
                    seen_set.add(t)
                    seen.append(t)

            scroll_top = await scroller.evaluate("el => el.scrollTop")
            await scroller.evaluate("el => el.scrollTop += el.clientHeight")
            await page.wait_for_timeout(120)

            new_scroll_top = await scroller.evaluate("el => el.scrollTop")
            if new_scroll_top == scroll_top or new_scroll_top == last_scroll_top:
                break
            last_scroll_top = new_scroll_top

        print(f"[DEBUG] total collected: {len(seen)}")
        for i, t in enumerate(seen):
            print(f"{i}: {t}")

        return seen


# -------------------------
# Pytest (same module)
# Run: pytest -q src/get_symbols.py
# -------------------------


@pytest.mark.asyncio
async def test_get_spot_symbols_contains_common_pairs():
    async with BybitHistoryClient(
        browser_name="firefox",
        headless=False,
    ) as client:
        await client.show_spot_symbols()


@pytest.mark.asyncio
async def test_get_contract_symbols_contains_common_pairs():
    async with BybitHistoryClient(
        browser_name="firefox",
        headless=False,
    ) as client:
        await client.show_contract_symbols()


@pytest.mark.asyncio
async def test_get_spot_data():
    async with BybitHistoryClient(
        browser_name="firefox",
        headless=False,
    ) as client:
        final_path = "/home/pasha/projects/bybit_data_puller/data"
        symbol = "BTCUSDT"
        start_date = "2026-01-01"
        end_date = "2026-01-05"
        margin = "Spot"
        data_type = "Trades"
        await client.download_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            margin=margin,
            data_type=data_type,
            final_path=final_path,
            chunk_days=2,
        )


@pytest.mark.asyncio
async def test_get_contract_data():
    async with BybitHistoryClient(
        browser_name="firefox",
        headless=False,
    ) as client:
        final_path = "/home/pasha/projects/bybit_data_puller/data"
        symbol = "BTCUSDT"
        start_date = "2026-01-01"
        end_date = "2026-01-05"
        margin = "Contract"
        data_type = "Trades"
        await client.download_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            margin=margin,
            data_type=data_type,
            final_path=final_path,
            chunk_days=2,
        )


@pytest.mark.asyncio
async def test_get_spot_data_l2():
    async with BybitHistoryClient(
        browser_name="firefox",
        headless=False,
    ) as client:
        final_path = "/home/pasha/projects/bybit_data_puller/data"
        symbol = "BTCUSDT"
        start_date = "2026-01-01"
        end_date = "2026-01-03"
        margin = "Spot"
        data_type = "L2Book"
        await client.download_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            margin=margin,
            data_type=data_type,
            final_path=final_path,
            chunk_days=2,
        )


@pytest.mark.asyncio
async def test_get_contract_data_l2():
    async with BybitHistoryClient(
        browser_name="firefox",
        headless=False,
    ) as client:
        final_path = "/home/pasha/projects/bybit_data_puller/data"
        symbol = "BTCUSDT"
        start_date = "2026-01-01"
        end_date = "2026-01-05"
        margin = "Spot"
        data_type = "L2Book"
        await client.download_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            margin=margin,
            data_type=data_type,
            final_path=final_path,
            chunk_days=2,
        )
