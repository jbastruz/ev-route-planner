---
name: ev-route
description: Plan an EV route with charging stops and a Google Maps visualization. Use this skill when the user asks for an itinerary, route, or trip planning for an electric vehicle (e.g., "itinerary from X to Y", "trip from X to Y", "how do I drive from X to Y with my EV"). Requires HERE_API_KEY environment variable and the `ev-route-planner` plugin's `here-ev` MCP server.
---

# EV Route Planning Workflow

Use this skill whenever the user asks for driving directions or an itinerary, especially for electric vehicles. The workflow is designed to produce a route plan with realistic charging stops and a visual map the user can share or push to their vehicle.

## Prerequisite — vehicle selection

Before planning, you need to know which EV the user has. Ask once per session (unless already known):

1. Call `mcp__here-ev__list_vehicles` to show available models.
2. Ask the user which one matches their car, or accept an override via `vehicle_id`.
3. If the user provides a brand/model not in the catalog, pick the closest match and note it.

If the user's vehicle is persistently stored (e.g., via memory), use that instead of asking again.

## Workflow (strict order)

### 1. Plan the route on HERE
Call `mcp__here-ev__plan_route` with:
- `origin`: place name, address, or `"lat,lng"`
- `destination`: same format
- `vehicle_id`: from the catalog (defaults to `polestar-2-lr-dual`)
- `initial_soc_pct`: user's current battery % at departure (default 90 if unknown)
- `min_arrival_soc_pct`: default 15 (safety margin)

The tool returns: distance, duration (driving + charging), list of `charge_stops` with full details, and a ready-made `google_maps_url` with waypoints.

### 2. Extract and format the stops
Parse the response. For each stop capture:
- Brand/name of the station
- Coordinates
- Max power (kW)
- SoC before → after (%)
- Duration (minutes)
- Arrival time

**Do NOT mention any total energy consumption number**. HERE's `consumption` field is unreliable (it underestimates by ~40%). Report only distance, time, and charging stops — not absolute energy or cost.

### 3. Render on Google Maps (optional but default)
Open the `google_maps_url` returned by `plan_route` in Playwright:
- Append `/@<centre_lat>,<centre_lng>,<zoom>z/data=!4m2!4m1!3e0` to center the map and force car mode
- Zoom: 7-7.5z for 400-600 km, 8-9z for 100-300 km, 10-11z for <100 km
- Use `mcp__playwright__browser_navigate` → wait 3s for load
- Click the "Réduire le panneau latéral" / "Collapse side panel" button via `mcp__playwright__browser_evaluate` to hide the sidebar
- Take a viewport screenshot with `mcp__playwright__browser_take_screenshot`
- Close the browser when done

### 4. Report back to the user
Send a concise message with:
- 🚗 Origin → Destination
- Distance, driving duration, charging duration, total door-to-door time
- Compact list of charging stops (time, brand, kW, SoC in→out, minutes)
- Relevant practical info (tolls, border crossing, Swiss vignette if applicable)
- Estimated arrival time if departure is "now"
- Attach the screenshot PNG

### Rules
- **Do NOT include the Google Maps URL by default** — only if the user asks for it explicitly ("give me the link", "send to my car", etc.). Many users prefer just the visual + summary.
- **Do NOT suggest ABRP or other planners** as alternatives. This skill uses HERE as the sole provider.
- Clean up temporary screenshot files after sending.
- If the route is shorter than the vehicle's autonomy (no stops needed), skip section 2's charging list and state "no charging needed, estimated arrival at X% SoC".

## Example invocation

User: *"Plan my trip from Nyon to Fréjus, I'm leaving with 85% battery"*

1. Confirm vehicle (or use persisted choice).
2. `plan_route(origin="Nyon", destination="Fréjus", vehicle_id="polestar-2-lr-dual", initial_soc_pct=85)`.
3. Open returned URL in Playwright + screenshot.
4. Reply with formatted summary + attached screenshot.
