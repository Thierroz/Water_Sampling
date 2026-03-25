#!/usr/bin/env python3
"""
water_temp.py
-------------
Fetches the current water temperature for a chosen Swiss hydrology station
and also the air temperature from the nearest MeteoSwiss (SMN) weather station.

APIs used:
  - BAFU/FOEN Hydrology : https://api.existenz.ch/apiv1/hydro/
  - MeteoSwiss SwissMetNet: https://api.existenz.ch/apiv1/smn/

Usage:
    python water_temp.py                           # interactive station menu
    python water_temp.py --place "Sihl"            # search by river name
    python water_temp.py --place "Zürich"          # search by town name
"""

import sys
import re
import math
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Tuple

try:
    import requests
except ImportError:
    print("Missing dependency. Please install it with:")
    print("  pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HYDRO_BASE = "https://api.existenz.ch/apiv1/hydro"
SMN_BASE   = "https://api.existenz.ch/apiv1/smn"
OUTPUT_DIR = Path(__file__).parent

HEADERS = {
    "User-Agent": "water_temp_script/3.0",
    "Accept":     "application/json",
}


# ---------------------------------------------------------------------------
# Hydro API helpers
# ---------------------------------------------------------------------------
def fetch_hydro_locations() -> Dict[str, dict]:
    resp = requests.get(f"{HYDRO_BASE}/locations", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return {k: v["details"] for k, v in resp.json()["payload"].items()}


def fetch_hydro_temperatures() -> Dict[str, dict]:
    resp = requests.get(
        f"{HYDRO_BASE}/latest",
        headers=HEADERS,
        params={"parameters": "temperature"},
        timeout=15,
    )
    resp.raise_for_status()
    return {
        e["loc"]: {"value": e["val"], "timestamp": e["timestamp"]}
        for e in resp.json()["payload"]
        if e["par"] == "temperature"
    }


def build_hydro_stations(locations, temperatures) -> List[dict]:
    stations = []
    for loc_id, temp_data in temperatures.items():
        if loc_id not in locations:
            continue
        loc = locations[loc_id]
        lat = loc.get("lat")
        lon = loc.get("lon")
        if not lat or not lon:
            continue
        stations.append({
            "id":         loc_id,
            "name":       loc.get("name", loc_id),
            "water_body": loc.get("water-body-name", ""),
            "body_type":  loc.get("water-body-type", ""),
            "lat":        lat,
            "lon":        lon,
            "value":      temp_data["value"],
            "timestamp":  temp_data["timestamp"],
        })
    stations.sort(key=lambda s: s["name"].lower())
    return stations


# ---------------------------------------------------------------------------
# SMN API helpers
# ---------------------------------------------------------------------------
def fetch_smn_locations() -> Dict[str, dict]:
    """Return dict of SMN station_id → details (name, lat, lon, canton)."""
    resp = requests.get(f"{SMN_BASE}/locations", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    result = {}
    for k, v in resp.json()["payload"].items():
        d = v.get("details", {})
        lat = d.get("lat")
        lon = d.get("lon")
        if lat and lon:
            result[k] = {
                "name":   d.get("name", k),
                "canton": d.get("canton", ""),
                "alt":    d.get("alt"),
                "lat":    lat,
                "lon":    lon,
            }
    return result


def fetch_smn_air_temperature(station_id: str) -> Optional[dict]:
    """
    Fetch the latest air temperature ('tt') for a given SMN station.
    Returns {value, timestamp} or None.
    """
    resp = requests.get(
        f"{SMN_BASE}/latest",
        headers=HEADERS,
        params={"locations": station_id, "parameters": "tt"},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json().get("payload", [])
    for entry in payload:
        if entry.get("par") == "tt":
            return {"value": entry["val"], "timestamp": entry["timestamp"]}
    return None


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_smn_station(
    lat: float, lon: float, smn_locations: Dict[str, dict]
) -> Tuple[str, dict, float]:
    """Return (station_id, details, distance_km) of the closest SMN station."""
    best_id, best_loc, best_dist = None, None, float("inf")
    for sid, loc in smn_locations.items():
        d = haversine_km(lat, lon, loc["lat"], loc["lon"])
        if d < best_dist:
            best_dist = d
            best_id   = sid
            best_loc  = loc
    return best_id, best_loc, best_dist


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sanitize_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\s]', "_", text)


def format_timestamp(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M %Z")


def choose_station(stations: List[dict], requested: Optional[str]) -> dict:
    if requested:
        q = requested.strip().lower()
        for s in stations:
            if s["name"].lower() == q:
                return s
        matches = [
            s for s in stations
            if q in s["name"].lower() or q in s["water_body"].lower()
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print(f"\n'{requested}' matches {len(matches)} stations:\n")
            for i, s in enumerate(matches, 1):
                print(f"  {i:>3}. {s['name']:<30}  ({s['water_body']})")
            print()
            while True:
                try:
                    idx = int(input("Enter number to select: ").strip()) - 1
                    if 0 <= idx < len(matches):
                        return matches[idx]
                    print(f"Please enter a number between 1 and {len(matches)}.")
                except ValueError:
                    print("Please enter a valid number.")
                except KeyboardInterrupt:
                    print("\nAborted.")
                    sys.exit(0)
        print(f"\nNo station found matching '{requested}'.")
        print("Run without --place to see the full list.")
        sys.exit(1)

    print(f"\nAvailable stations ({len(stations)} total):\n")
    for i, s in enumerate(stations, 1):
        body = f"{s['water_body']} ({s['body_type']})" if s["water_body"] else ""
        print(f"  {i:>3}. {s['name']:<30}  {body}")
    print()

    while True:
        try:
            idx = int(input("Enter station number: ").strip()) - 1
            if 0 <= idx < len(stations):
                return stations[idx]
            print(f"Please enter a number between 1 and {len(stations)}.")
        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(0)


def save_result(station: dict, air_info: Optional[dict]) -> Path:
    now       = datetime.now()
    date_str  = now.strftime("%Y-%m-%d")
    time_str  = now.strftime("%H-%M-%S")
    place_str = sanitize_filename(station["name"])

    filename = f"{date_str}_{time_str}_{place_str}.txt"
    filepath = OUTPUT_DIR / filename

    lines = [
        f"Measurement Station  : {station['name']}",
        f"Water Body           : {station['water_body']} ({station['body_type']})",
        f"Coordinates          : lat {station['lat']}, lon {station['lon']}",
        f"Measured at (source) : {format_timestamp(station['timestamp'])}",
        f"Script run at (local): {now.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Water Temperature    : {station['value']:.2f} °C",
    ]

    if air_info:
        lines += [
            "",
            f"Nearest SMN Station  : {air_info['smn_name']} ({air_info['smn_id']}, "
            f"canton {air_info['smn_canton']}, {air_info['smn_dist_km']:.1f} km away)",
            f"Air Temp (SMN)       : {air_info['value']:.1f} °C",
            f"Air Temp measured at : {format_timestamp(air_info['timestamp'])}",
        ]
    else:
        lines.append("")
        lines.append("Air Temperature      : not available")

    lines += [
        "",
        f"Hydro source : {HYDRO_BASE}",
        f"SMN source   : {SMN_BASE}",
        f"Data         : BAFU/FOEN (hydrology) & MeteoSwiss/SwissMetNet (weather)",
    ]

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Fetch Swiss water temperature (BAFU) + nearest air temperature (MeteoSwiss)."
    )
    parser.add_argument(
        "--place", "-p",
        metavar="NAME",
        help='Station name, town, or river (partial match supported, e.g. "Sihl")',
    )
    args = parser.parse_args()

    print("Fetching hydro station list …")
    hydro_locs = fetch_hydro_locations()

    print("Fetching latest water temperatures …")
    hydro_temps = fetch_hydro_temperatures()

    stations = build_hydro_stations(hydro_locs, hydro_temps)
    print(f"Found {len(stations)} active water temperature stations.\n")

    station = choose_station(stations, args.place)

    # ---- Fetch nearest SMN air temperature -----------------------------------
    print("\nFetching SMN weather station list …")
    smn_locs = fetch_smn_locations()

    smn_id, smn_loc, smn_dist = nearest_smn_station(
        station["lat"], station["lon"], smn_locs
    )

    print(f"Nearest SMN station  : {smn_loc['name']} ({smn_id}), {smn_dist:.1f} km away")
    print("Fetching air temperature …")
    air_raw = fetch_smn_air_temperature(smn_id)

    air_info = None
    if air_raw:
        air_info = {
            "smn_id":       smn_id,
            "smn_name":     smn_loc["name"],
            "smn_canton":   smn_loc["canton"],
            "smn_dist_km":  smn_dist,
            "value":        air_raw["value"],
            "timestamp":    air_raw["timestamp"],
        }

    # ---- Display -------------------------------------------------------
    print()
    print(f"Station              : {station['name']}")
    print(f"Water Body           : {station['water_body']} ({station['body_type']})")
    print(f"Water Temp measured  : {format_timestamp(station['timestamp'])}")
    print(f"Water Temperature    : {station['value']:.2f} °C")
    print()
    if air_info:
        print(f"Nearest SMN station  : {air_info['smn_name']} ({smn_id}), {smn_dist:.1f} km")
        print(f"Air Temp measured    : {format_timestamp(air_info['timestamp'])}")
        print(f"Air Temperature      : {air_info['value']:.1f} °C")
    else:
        print("Air Temperature      : not available from nearest SMN station")

    filepath = save_result(station, air_info)
    print(f"\n✅  Saved to: {filepath}")


if __name__ == "__main__":
    main()
