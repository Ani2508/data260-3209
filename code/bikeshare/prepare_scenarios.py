"""HW7 Part 4 - build the two scenario CSVs from public Citi Bike trip data.

Source: Citi Bike System Data (https://citibikenyc.com/system-data), Jersey City monthly file
from https://s3.amazonaws.com/tripdata/. Public data has no rider id, so each scenario assigns
its real trips to a fixed number of riders (rider_id) with a seeded RNG; nothing else is changed.

  Scenario A (membership should win): 520 member trips >= 8 min, classic + e-bike, 8 riders.
  Scenario B (pay-per-use should win): 520 casual classic trips <= 15 min, 260 riders (2 each).

Usage:  python -m bikeshare.prepare_scenarios      (run from code/)
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import statistics
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "bikeshare"                      # downloaded zip (git-ignored)
CASES = ROOT / "reports" / "hw07" / "cases"
RAW_OUT = ROOT / "reports" / "hw07" / "raw"
SEED = 3209
N_TRIPS = 520
BASE = "https://s3.amazonaws.com/tripdata/JC-{ym}-citibike-tripdata.csv.zip"
KEEP = ["ride_id", "rider_id", "rideable_type", "started_at", "ended_at",
        "start_station_name", "end_station_name", "member_casual"]


def candidate_months(today: date | None = None, back: int = 18) -> list[str]:
    """Return YYYYMM strings from last month backwards."""
    today = today or date.today()
    y, m, out = today.year, today.month, []
    for _ in range(back):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append(f"{y}{m:02d}")
    return out


def download() -> tuple[Path, str]:
    """Return (zip path, url) of the newest available Jersey City monthly file."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for ym in candidate_months():
        url = BASE.format(ym=ym)
        dest = RAW_DIR / Path(url).name
        if dest.exists():
            return dest, url
        try:
            with urllib.request.urlopen(url, timeout=60) as r:   # noqa: S310 (fixed public URL)
                dest.write_bytes(r.read())
            return dest, url
        except Exception as exc:
            print(f"  {ym}: not available ({type(exc).__name__})")
    raise SystemExit("no Jersey City monthly file found in the last 18 months")


def read_trips(zpath: Path) -> list[dict]:
    """Return the trips in the monthly zip with a computed duration (minutes)."""
    with zipfile.ZipFile(zpath) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv") and "MACOSX" not in n)
        rows = list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8")))
    out = []
    for r in rows:
        try:
            dur = (datetime.fromisoformat(r["ended_at"]) -
                   datetime.fromisoformat(r["started_at"])).total_seconds() / 60
        except (KeyError, ValueError):
            continue
        if 1 <= dur <= 180:                     # drop broken / docked-overnight records
            r["_dur"] = dur
            out.append(r)
    return out


def build(trips: list[dict], name: str, pick, riders: int, out: Path) -> dict:
    """Write one scenario CSV; return its summary for raw/."""
    rng = random.Random(f"{SEED}-{name}")
    pool = [t for t in trips if pick(t)]
    if len(pool) < N_TRIPS:
        raise SystemExit(f"{name}: only {len(pool)} matching trips (need {N_TRIPS})")
    chosen = sorted(rng.sample(pool, N_TRIPS), key=lambda t: t["started_at"])
    if N_TRIPS % riders:
        raise ValueError(f"{N_TRIPS} trips cannot be split evenly over {riders} riders")
    ids = [f"rider_{i + 1:03d}" for i in range(riders)] * (N_TRIPS // riders)  # equal share
    rng.shuffle(ids)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KEEP)
        w.writeheader()
        for t, rid in zip(chosen, ids, strict=False):
            w.writerow({**{k: t.get(k, "") for k in KEEP}, "rider_id": rid})
    durs = [t["_dur"] for t in chosen]
    distinct = len(set(ids))
    return {"scenario": name, "file": str(out.relative_to(ROOT)), "rows": len(chosen),
            "riders": distinct, "rides_per_rider": round(len(chosen) / distinct, 2),
            "first_start": chosen[0]["started_at"], "last_start": chosen[-1]["started_at"],
            "avg_duration_min": round(statistics.mean(durs), 2),
            "median_duration_min": round(statistics.median(durs), 2),
            "max_duration_min": round(max(durs), 2),
            "over_30_min": sum(d > 30 for d in durs), "over_45_min": sum(d > 45 for d in durs),
            "ebike_share": round(sum(t["rideable_type"] == "electric_bike"
                                     for t in chosen) / len(chosen), 3),
            "member_casual": {k: sum(t["member_casual"] == k for t in chosen)
                              for k in ("member", "casual")},
            "csv_sha256": hashlib.sha256(out.read_bytes()).hexdigest()}


def main() -> None:
    zpath, url = download()
    trips = read_trips(zpath)
    print(f"source: {url}  ({len(trips)} valid trips)")
    CASES.mkdir(parents=True, exist_ok=True)
    RAW_OUT.mkdir(parents=True, exist_ok=True)
    source = {"url": url, "zip_sha256": hashlib.sha256(zpath.read_bytes()).hexdigest(),
              "downloaded_at": datetime.now().isoformat(timespec="seconds"),
              "valid_trips_in_month": len(trips),
              "note": "rider_id is assigned by this script (public data has no rider id)"}
    a = build(trips, "A_membership_wins",
              lambda t: t["member_casual"] == "member" and t["_dur"] >= 8, 8,
              CASES / "part4_scenarioA_trips.csv")
    b = build(trips, "B_pay_per_use_wins",
              lambda t: (t["member_casual"] == "casual" and t["rideable_type"] == "classic_bike"
                         and t["_dur"] <= 15), 260,
              CASES / "part4_scenarioB_trips.csv")
    for s in (a, b):
        s["source"] = source
        path = RAW_OUT / f"part4_scenario{s['scenario'][0]}_trip_summary.json"
        path.write_text(json.dumps(s, indent=2))
        print(f"  {s['scenario']}: {s['rows']} trips, {s['riders']} riders, "
              f"{s['rides_per_rider']} rides/rider, avg {s['avg_duration_min']} min, "
              f"e-bike {s['ebike_share']:.0%} -> {s['file']}")


if __name__ == "__main__":
    main()
