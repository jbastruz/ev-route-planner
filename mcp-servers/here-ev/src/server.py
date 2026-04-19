"""HERE EV Routing MCP server.

Exposes tools for planning EV routes with charging stops using the HERE Routing API v8
with EV-specific consumption and charging parameters.

Environment:
    HERE_API_KEY: required, your HERE Developer API key (https://platform.here.com)

Tools:
    plan_route         Plan an EV route with charging stops
    geocode_place      Resolve place name/address to lat/lng
    list_vehicles      List supported vehicle models from the plugin catalog
    get_vehicle        Get full specs for a specific vehicle id
"""

import json
import logging
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("here-ev-mcp")
mcp = FastMCP("here-ev")

VEHICLES_DIR = Path(
    os.environ.get(
        "EV_ROUTE_VEHICLES_DIR",
        str(Path(__file__).resolve().parent.parent.parent.parent / "vehicles"),
    )
)
CACHE_PATH = Path(
    os.environ.get(
        "EV_ROUTE_GEOCODE_CACHE",
        str(Path.home() / ".ev-route-planner" / "geocode-cache.json"),
    )
)
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _require_key() -> str:
    key = os.environ.get("HERE_API_KEY")
    if not key:
        raise RuntimeError(
            "HERE_API_KEY environment variable is not set. "
            "Get a key at https://platform.here.com and export it before running."
        )
    return key


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def _load_vehicle(vehicle_id: str) -> dict:
    path = VEHICLES_DIR / f"{vehicle_id}.json"
    if not path.exists():
        available = [p.stem for p in VEHICLES_DIR.glob("*.json")]
        raise ValueError(
            f"Unknown vehicle id '{vehicle_id}'. Available: {', '.join(sorted(available))}"
        )
    return json.loads(path.read_text())


def _http_get(url: str, timeout: int = 30) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"HERE API HTTP {e.code}: {body}")


@mcp.tool()
def geocode_place(query: str) -> dict:
    """Resolve a place name or address to lat/lng coordinates via HERE Geocoding.

    Results are cached on disk to avoid redundant API calls. If `query` is already a
    "lat,lng" string it is returned as-is without calling the API.

    Args:
        query: A place name, address, or "lat,lng" coordinates.

    Returns:
        dict with keys: lat, lng, label, cached (bool).
    """
    q = query.strip()

    # Pass-through if already coords
    if "," in q:
        parts = [p.strip() for p in q.split(",")]
        if len(parts) == 2:
            try:
                return {"lat": float(parts[0]), "lng": float(parts[1]), "label": q, "cached": False}
            except ValueError:
                pass

    cache = _load_cache()
    key = q.lower()
    if key in cache:
        entry = cache[key]
        return {"lat": entry["lat"], "lng": entry["lng"], "label": entry["label"], "cached": True}

    params = {"q": q, "limit": 1, "apiKey": _require_key()}
    data = _http_get("https://geocode.search.hereapi.com/v1/geocode?" + urllib.parse.urlencode(params))
    items = data.get("items", [])
    if not items:
        raise ValueError(f"No results for '{q}'")

    item = items[0]
    result = {
        "lat": item["position"]["lat"],
        "lng": item["position"]["lng"],
        "label": item.get("title", q),
        "cached": False,
    }

    cache[key] = {"lat": result["lat"], "lng": result["lng"], "label": result["label"]}
    _save_cache(cache)

    return result


@mcp.tool()
def list_vehicles() -> list:
    """List all supported EV models in the plugin catalog.

    Returns:
        List of {id, name, battery_usable_kwh, max_dc_charge_kw} summaries.
    """
    result = []
    for path in sorted(VEHICLES_DIR.glob("*.json")):
        v = json.loads(path.read_text())
        result.append({
            "id": v["id"],
            "name": v["name"],
            "battery_usable_kwh": v["battery_usable_kwh"],
            "max_dc_charge_kw": v["max_dc_charge_kw"],
        })
    return result


@mcp.tool()
def get_vehicle(vehicle_id: str) -> dict:
    """Get full specs (battery, consumption tables, charging curve) for a vehicle.

    Args:
        vehicle_id: The vehicle id (e.g. "polestar-2-lr-dual"). Use list_vehicles to discover.

    Returns:
        Full vehicle spec dict.
    """
    return _load_vehicle(vehicle_id)


@mcp.tool()
def plan_route(
    origin: str,
    destination: str,
    vehicle_id: str = "polestar-2-lr-dual",
    initial_soc_pct: int = 90,
    min_arrival_soc_pct: int = 15,
    max_charge_soc_pct: int = 80,
) -> dict:
    """Plan an EV route from origin to destination with automatic charging stops.

    Uses HERE Routing v8 with EV params (consumption tables, charging curve, connector types).
    If origin or destination is not "lat,lng", it is geocoded via HERE Geocoding.

    Args:
        origin: Place name, address, or "lat,lng".
        destination: Place name, address, or "lat,lng".
        vehicle_id: Vehicle catalog id (default: polestar-2-lr-dual). Use list_vehicles for options.
        initial_soc_pct: Starting state of charge, 0-100 (default: 90).
        min_arrival_soc_pct: Minimum state of charge at destination, 0-100 (default: 15).
        max_charge_soc_pct: Maximum state of charge after a charging stop, 0-100 (default: 80).

    Returns:
        dict with:
            origin, destination: resolved place labels + coords
            vehicle: vehicle name + battery info
            distance_km, duration_driving_s, duration_charging_s, duration_total_s
            charge_stops: list of {name, brand, lat, lng, power_kw, arrival_time,
                                    arrival_soc_kwh, target_soc_kwh,
                                    arrival_soc_pct, target_soc_pct, duration_s}
            google_maps_url: a Google Maps directions URL with the stops as waypoints
    """
    vehicle = _load_vehicle(vehicle_id)

    origin_geo = geocode_place(origin)
    dest_geo = geocode_place(destination)

    battery = vehicle["battery_total_kwh"]
    initial_charge = battery * initial_soc_pct / 100
    min_at_destination = battery * min_arrival_soc_pct / 100
    min_at_station = battery * 0.10
    max_after_charge = battery * max_charge_soc_pct / 100

    params = {
        "transportMode": "car",
        "origin": f"{origin_geo['lat']},{origin_geo['lng']}",
        "destination": f"{dest_geo['lat']},{dest_geo['lng']}",
        "return": "summary,polyline",
        "ev[freeFlowSpeedTable]": vehicle["freeFlowSpeedTable"],
        "ev[trafficSpeedTable]": vehicle["trafficSpeedTable"],
        "ev[auxiliaryConsumption]": str(vehicle["auxiliaryConsumption"]),
        "ev[ascent]": str(vehicle["ascent"]),
        "ev[descent]": str(vehicle["descent"]),
        "ev[makeReachable]": "true",
        "ev[connectorTypes]": vehicle["connector"],
        "ev[chargingCurve]": vehicle["charging_curve"],
        "ev[maxCharge]": str(battery),
        "ev[initialCharge]": str(initial_charge),
        "ev[maxChargeAfterChargingStation]": str(max_after_charge),
        "ev[minChargeAtChargingStation]": str(min_at_station),
        "ev[minChargeAtDestination]": str(min_at_destination),
        "apiKey": _require_key(),
    }

    result = _http_get("https://router.hereapi.com/v8/routes?" + urllib.parse.urlencode(params))

    if not result.get("routes"):
        raise RuntimeError(f"No route found: {result}")

    route = result["routes"][0]
    sections = route.get("sections", [])

    total_distance_m = 0
    total_duration_s = 0
    total_charge_s = 0
    charge_stops = []

    for s in sections:
        summary = s.get("summary", {})
        total_distance_m += summary.get("length", 0)
        total_duration_s += summary.get("duration", 0)
        for pa in s.get("postActions") or []:
            if pa.get("action") == "charging":
                total_charge_s += pa.get("duration", 0)
                arr = s.get("arrival", {})
                place = arr.get("place", {})
                charge_stops.append({
                    "name": place.get("name", "?"),
                    "brand": place.get("brand", {}).get("name", ""),
                    "lat": place.get("location", {}).get("lat"),
                    "lng": place.get("location", {}).get("lng"),
                    "power_kw": place.get("attributes", {}).get("power"),
                    "arrival_time": arr.get("time", ""),
                    "arrival_soc_kwh": pa.get("arrivalCharge", 0),
                    "target_soc_kwh": pa.get("targetCharge", 0),
                    "arrival_soc_pct": round(pa.get("arrivalCharge", 0) / battery * 100),
                    "target_soc_pct": round(pa.get("targetCharge", 0) / battery * 100),
                    "duration_s": pa.get("duration", 0),
                })

    # Google Maps directions URL with waypoints
    url_parts = [f"{origin_geo['lat']},{origin_geo['lng']}"]
    for cs in charge_stops:
        url_parts.append(f"{cs['lat']:.5f},{cs['lng']:.5f}")
    url_parts.append(f"{dest_geo['lat']},{dest_geo['lng']}")
    gmaps_url = "https://www.google.com/maps/dir/" + "/".join(url_parts)

    return {
        "origin": {"label": origin_geo["label"], "lat": origin_geo["lat"], "lng": origin_geo["lng"]},
        "destination": {"label": dest_geo["label"], "lat": dest_geo["lat"], "lng": dest_geo["lng"]},
        "vehicle": {
            "id": vehicle["id"],
            "name": vehicle["name"],
            "battery_total_kwh": vehicle["battery_total_kwh"],
            "battery_usable_kwh": vehicle["battery_usable_kwh"],
        },
        "initial_soc_pct": initial_soc_pct,
        "distance_km": round(total_distance_m / 1000, 1),
        "duration_driving_s": total_duration_s,
        "duration_charging_s": total_charge_s,
        "duration_total_s": total_duration_s + total_charge_s,
        "charge_stops": charge_stops,
        "google_maps_url": gmaps_url,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
