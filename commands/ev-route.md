---
description: Plan an EV route with charging stops. Usage: /ev-route <origin> <destination> [SoC%]
argument-hint: "<origin> <destination> [initial_soc_pct]"
---

Plan an electric-vehicle route from **$1** to **$2** using the `here-ev` MCP server.

1. Invoke `mcp__here-ev__plan_route` with:
   - `origin`: `$1`
   - `destination`: `$2`
   - `initial_soc_pct`: `$3` if provided, else `90`
   - `vehicle_id`: the user's persisted vehicle if known, else `polestar-2-lr-dual`
2. Open the returned `google_maps_url` in Playwright (`mcp__playwright__browser_navigate`), collapse the side panel, and take a screenshot.
3. Reply with a concise summary:
   - Origin → Destination
   - Distance, driving time, charging time, total door-to-door time
   - List of charge stops with time, brand, power, SoC in→out, duration
   - Attach the screenshot
4. Do not include the Google Maps URL unless the user asks for it.
5. Do not report any total energy consumption — HERE's consumption field is unreliable.
