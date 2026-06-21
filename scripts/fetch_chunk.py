"""
scripts/fetch_chunk.py
========================
Scheduled (cron) chunked universe refresh.

Replaces the idea of one giant "run all ~2640 NSE stocks" daily job (which
would take hours and risk hitting GitHub Actions' 6-hour job timeout, plus
hammering yfinance rate limits all at once) with small, frequent slices:
each scheduled run processes the NEXT ~140 symbols from a combined
main-board + SME universe list, then advances a persisted cursor so the
following run picks up where this one left off.

Universe order: data/universe/equity_main.csv (2091 EQ-series main-board
stocks) is fully cycled through before data/universe/equity_sme.csv (550
SME-board stocks) begins. At the default chunk size (165) and the scheduled
cadence (~90 min, 16 runs/day — see .github/workflows/scheduled_chunk.yml),
main board completes in ~13 chunks (~19.5h), leaving ~3 spare runs/day as a
buffer for SME coverage and for retrying any chunk that mostly failed
(see CURSOR ADVANCEMENT below) — SME then completes its own rotation in
roughly 1-2 days depending on how much of that buffer retries consume.

State: data/cursor.json holds {"position": <int>}, a simple absolute index
into the concatenated [main_universe + sme_universe] symbol list, wrapping
back to 0 after the last symbol. The cursor is only advanced on a (mostly)
successful run — see CURSOR ADVANCEMENT note below — so a failed run's slice
gets retried at the next scheduled trigger instead of being silently skipped
for a full rotation.

Each symbol's full fetch+score+value pipeline is the SAME analyze_stock()
used by the Streamlit single-stock tab and scripts/fetch_single.py — one
implementation, three callers (interactive UI, on-demand workflow, scheduled
chunks), so there is nothing to keep in sync across them.

Usage:
    python scripts/fetch_chunk.py
    python scripts/fetch_chunk.py --chunk-size 140
    python scripts/fetch_chunk.py --cursor-path data/cursor.json

Exit codes:
    0 = ran (even if some individual symbols failed — per-symbol failures are
        isolated and logged, matching fetch_universe()'s existing behavior)
    1 = hard failure (couldn't load universe files, couldn't read/write cursor)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.data_fetcher import YFinanceSource
from utils.analyzer import analyze_stock
from utils.exporter import write_chunk_to_export  # see exporter_chunk_addon.py — copy into exporter.py first

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fetch_chunk")

REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN_UNIVERSE_PATH = REPO_ROOT / "data" / "universe" / "equity_main.csv"
SME_UNIVERSE_PATH = REPO_ROOT / "data" / "universe" / "equity_sme.csv"
DEFAULT_CURSOR_PATH = REPO_ROOT / "data" / "cursor.json"
DEFAULT_CHUNK_SIZE = 165

# Be polite to yfinance across a chunk of ~140 sequential requests — same
# spirit as YFinanceSource's own jittered inter-request delay, applied here
# at the orchestration level too since analyze_stock() calls fetch() once
# per symbol in a tight loop below.
INTER_SYMBOL_DELAY_SEC = 0.3


def load_universe_list() -> list[tuple[str, str]]:
    """
    Returns the combined [main_board..., sme_board...] symbol list as
    (symbol, company_name) tuples, in a stable, deterministic order — main
    board fully precedes SME so main-board refresh cadence isn't diluted by
    interleaving the smaller, lower-priority SME list throughout it.
    """
    if not MAIN_UNIVERSE_PATH.exists():
        raise RuntimeError(f"Main universe file not found: {MAIN_UNIVERSE_PATH}")

    main_df = pd.read_csv(MAIN_UNIVERSE_PATH)
    combined = list(zip(main_df["Symbol"], main_df["Company Name"]))

    if SME_UNIVERSE_PATH.exists():
        sme_df = pd.read_csv(SME_UNIVERSE_PATH)
        combined += list(zip(sme_df["Symbol"], sme_df["Company Name"]))
    else:
        log.warning(f"SME universe file not found ({SME_UNIVERSE_PATH}) — proceeding with main board only.")

    return combined


def load_cursor(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("position", 0))
    except (json.JSONDecodeError, ValueError, OSError) as e:
        log.warning(f"Cursor file unreadable ({e}) — starting from position 0.")
        return 0


def save_cursor(path: Path, position: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"position": position}, indent=2), encoding="utf-8")


def run_chunk(chunk_size: int, cursor_path: Path) -> int:
    universe = load_universe_list()
    total = len(universe)
    if total == 0:
        raise RuntimeError("Universe list is empty — nothing to process.")

    start = load_cursor(cursor_path) % total
    # Wrap-around slice: if start + chunk_size overflows the list length,
    # take the tail then continue from the front, so the rotation is
    # continuous rather than leaving a short final chunk every cycle.
    end = start + chunk_size
    if end <= total:
        slice_symbols = universe[start:end]
    else:
        slice_symbols = universe[start:total] + universe[0:end - total]

    log.info(f"Universe size: {total} | cursor start: {start} | processing {len(slice_symbols)} symbols")

    source = YFinanceSource()
    rows = []
    deep_data = {}
    failures = []

    for i, (symbol, company) in enumerate(slice_symbols):
        try:
            fr = source.fetch(symbol, use_cache=True)  # cache IS used here (unlike fetch_single.py's
                                                          # on-demand path) — a scheduled chunk benefits
                                                          # from the 6h disk cache if a symbol was somehow
                                                          # already fetched recently (e.g. via manual search)
            if not fr.ok:
                failures.append((symbol, fr.error))
                continue

            analysis = analyze_stock(symbol, fr)
            if analysis is None:
                failures.append((symbol, "analyze_stock returned None"))
                continue

            rows.append(analysis["row"])
            deep_data[symbol] = analysis["deep"]

        except Exception as e:
            failures.append((symbol, str(e)))

        if i < len(slice_symbols) - 1:
            time.sleep(INTER_SYMBOL_DELAY_SEC)

    log.info(f"Chunk done: {len(rows)} succeeded, {len(failures)} failed")
    for sym, err in failures[:20]:  # cap log spam if a whole chunk fails
        log.warning(f"  {sym}: {err}")

    if rows:
        df = pd.DataFrame(rows)
        output_path, updated = write_chunk_to_export(df, deep_data, universe_label="NSE_ALL_CHUNKED")
        log.info(f"Merged {updated} symbols into {output_path}")
    else:
        log.warning("No symbols succeeded this chunk — latest.json not touched.")

    # CURSOR ADVANCEMENT: advance even if some individual symbols failed
    # (isolated per-symbol failures are expected and already logged above —
    # matching fetch_universe()'s existing "one bad ticker never kills the
    # run" philosophy). Only refuse to advance on a near-total wipeout, so a
    # systemic problem (e.g. yfinance fully down, bad token) doesn't silently
    # burn through the whole rotation marking everything "done" with no data.
    failure_rate = len(failures) / len(slice_symbols) if slice_symbols else 1.0
    if failure_rate >= 0.9:
        log.error(
            f"Failure rate {failure_rate:.0%} — NOT advancing cursor, "
            f"this chunk will be retried next run instead of being skipped."
        )
        return 1

    new_position = end % total
    save_cursor(cursor_path, new_position)
    log.info(f"Cursor advanced to position {new_position} (of {total})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--cursor-path", type=str, default=str(DEFAULT_CURSOR_PATH))
    args = parser.parse_args()

    try:
        return run_chunk(args.chunk_size, Path(args.cursor_path))
    except Exception as e:
        log.error(f"Hard failure: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
