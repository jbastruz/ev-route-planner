# ev-route-planner

A Claude Code plugin that plans electric-vehicle road trips with realistic charging stops and Google Maps visualizations.

Uses:
- [HERE Routing API v8](https://developer.here.com) for EV-aware route planning (consumption model, charging curves, real charging stations)
- [HERE Geocoding](https://developer.here.com) for place name resolution
- [Playwright MCP](https://github.com/microsoft/playwright-mcp) for Google Maps screenshots

## What it does

Ask Claude something like:

> Plan a trip from Nyon to Fréjus, I'm leaving with 50% battery.

The plugin will:
1. Resolve place names to coordinates (HERE Geocoding)
2. Compute an EV-aware route with automatic charging stops (HERE EV Routing with the vehicle's charging curve and real consumption model)
3. Render the resulting itinerary on Google Maps (Playwright screenshot)
4. Give you a concise summary: distance, driving time, charging time, and every stop (brand, kW, SoC before/after, minutes)

## Installation

### Prerequisites
- Python 3.10+
- A HERE Developer API key (free tier: 250k requests/month). Sign up at [platform.here.com](https://platform.here.com) and create an API key under **Projects → Access Manager → API Keys**.
- [Playwright MCP server](https://github.com/microsoft/playwright-mcp) installed in Claude Code (for the screenshot step).

### Install the plugin
```bash
# Clone the repo
git clone https://github.com/jbastruz/ev-route-planner.git ~/.claude/plugins/ev-route-planner

# Install the MCP server's Python deps
cd ~/.claude/plugins/ev-route-planner/mcp-servers/here-ev
pip install -e .
```

### Configure the API key
Export your HERE key in your shell:
```bash
export HERE_API_KEY="your-here-api-key"
```

Or add it to your `~/.claude/settings.json` under `env`:
```json
{
  "env": {
    "HERE_API_KEY": "your-here-api-key"
  }
}
```

### Enable the plugin
Add to `~/.claude/settings.json`:
```json
{
  "plugins": {
    "ev-route-planner": {
      "path": "~/.claude/plugins/ev-route-planner"
    }
  }
}
```

Or use `/plugin` inside Claude Code to enable it interactively.

## Usage

### As a skill (natural language)
Just ask Claude:
- "Plan my trip from Lausanne to Milan, 80% battery at start"
- "How do I drive from Paris to Lyon with my EV?"
- "Itinerary Nyon → Zurich"

The `ev-route` skill will trigger and run the full workflow.

### As a slash command
```
/ev-route "Nyon" "Fréjus" 85
```

### Direct MCP tool calls
The plugin exposes four tools on the `here-ev` MCP server:
- `plan_route(origin, destination, vehicle_id, initial_soc_pct, ...)` — compute the full route with stops
- `geocode_place(query)` — resolve a place name/address to coordinates
- `list_vehicles()` — list all supported EV models
- `get_vehicle(vehicle_id)` — get full specs for one vehicle

## Supported vehicles

**35 models** shipped, all European CCS2 connector (`iec62196Type2Combo`).

**Tesla** — Model 3 RWD/LR AWD (Highland), Model Y RWD/LR AWD, Model S LR Plaid
**Polestar** — 2 SR Single / 2 LR Dual, 3 LR Dual, 4 LR Single
**Volkswagen** — ID.3 Pro S, ID.4 Pro, ID.7 Pro, ID.Buzz Pro
**BMW** — i4 eDrive40, iX xDrive40, iX1 xDrive30
**Mercedes** — EQA 300 4MATIC, EQE 350+, EQS 450+
**Hyundai** — Ioniq 5 LR AWD, Ioniq 6 LR AWD, Kona Electric 65
**Kia** — EV6 LR AWD GT-Line, EV9 GT-Line AWD, Niro EV 64
**Audi** — Q4 e-tron 45, e-tron GT Quattro
**Renault** — Mégane E-Tech EV60, Scenic E-Tech 87
**Others** — Peugeot e-308 54, Škoda Enyaq iV 85, Ford Mustang Mach-E ER AWD, Volvo EX30 Twin Performance, Nissan Ariya 87 e-4ORCE, MG4 Electric LR 77

Use `list_vehicles` MCP tool to get the full list with ids, battery, and peak DC power.

Contributions welcome — add a JSON file under `vehicles/` following the existing schema. Sources: [ev-database.org](https://ev-database.org), [evkx.net](https://evkx.net), [Fastned charging curves](https://fastnedcharging.com/hq/charging-curves).

## Why HERE and not ABRP?

ABRP has a more sophisticated EV model, but its Planning API is a negotiated commercial product (no self-serve free tier). HERE's EV Routing offers:
- 250k free requests / month, self-serve
- Vehicle-aware consumption (speed tables + ascent/descent + auxiliary load)
- Real charging station database with live availability and connector filtering
- Integrated traffic and routing quality

For "where and when to stop" planning, HERE is accurate enough. For vehicle telemetry or ultra-precise energy predictions, you might still want ABRP.

## Known limitations

- HERE's `summary.consumption` field underestimates by ~40% on mountain routes. **Do not use it as an energy total** — the plugin's skill explicitly tells Claude to ignore it and only report time/distance/stops.
- The charging curves in `vehicles/*.json` are approximations. Real-world performance depends on battery temperature, pack age, and charger throttling.
- Europe-first: all vehicles use CCS2 (`iec62196Type2Combo`). Adding non-European markets means adding vehicles with `chademo` or `j1772ccs` connectors.

## Contributing

- New vehicles: add a JSON under `vehicles/` with specs from ev-database.org + Fastned measured curves.
- Bug reports and feature requests: GitHub Issues.
- PRs: welcome with tests.

## License

MIT © 2026 Jean-Baptiste ASTRUZ
