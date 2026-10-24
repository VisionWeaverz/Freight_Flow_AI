# Geographic replay assets

The fourth dashboard tab replays the active shipment and up to five additional
shipments. Operations, Recovery & Approval, and the map use one shared scenario
selector above the tabs. `scenario.py` reads a fresh shipment/pricing snapshot on
each rerun and computes exposure and plans once for all views. Changing shipment,
disruption, delay, bookings, or tariffs invalidates the old approval and explanations.

- `replay.html`: Leaflet 1.9.4 map, vehicle animation, replay controls, event log,
  financial exposure, and recovery previews. Python injects a JSON payload into
  the template; no operational approval or database mutation occurs here.
- `jnpt_bhiwandi_route.json`: 64.4 km illustrative driving geometry obtained from
  the public OSRM routing service using OpenStreetMap data on 24 October 2026.
  Endpoints are illustrative facility locations, not verified customer addresses.
  This is a bundled route, not a real-time routing or traffic feed.
- `route_*.json`: additional OSRM/OpenStreetMap road geometries for all combinations
  of the five seeded origin ports and five destination hubs. Retrieved 24 October
  2026 using illustrative facility coordinates. Attribution is displayed on the map.

Leaflet loads from unpkg. Road tiles come from OpenStreetMap; satellite imagery
comes from Esri World Imagery. Attribution is displayed on the map. Internet
access is required for the map library and basemap tiles. A visible message is
shown if these cannot load, while timeline controls and financial data still work.

Vehicle positions are interpolated along the stored route using simulated time.
The short final-mile segment and vessel approach are illustrative. Road incidents
pause the truck along the route; port incidents hold the vessel offshore. The
unmitigated milestone times and final penalties come from `build_cascade_graph`.

Recovery plans come from `CentralCoordinator`. As `RecoveryPlan` does not expose
per-milestone timestamps, recovery animation derives a sequential preview from
the chosen berth, carrier, and warehouse actions. Morning intake waits until the
next available 08:00 slot. These preview timestamps are distinct from the
coordinator's aggregate delay metric, which is labelled separately. Recovery
operating fees exclude residual delivery penalties; they are not labelled total
landed costs or guaranteed savings.

Controls: choose the active consignment, disruption, and duration above the tabs.
Use the map multiselect to add independent shipment comparisons. Each uses its own
bookings and applied tariffs with the same disruption/duration; comparisons are
aligned by elapsed time and are not a joint fleet allocation simulation.
Play/Pause, Step, Replay,
or scrub below it. Choose Road/Satellite and Corridor/Port/Follow Truck views.
Click facilities or vehicles for details. Click Cheapest/Fastest/Safest to preview
recovery at the same simulation time, or restart to replay it from the beginning.

Verification (isolated databases; preserves the app's active tariffs):

```sh
./venv/bin/pytest tests/test_shared_scenario.py tests/test_map_simulation.py tests/test_recovery_pricing.py -q
```
