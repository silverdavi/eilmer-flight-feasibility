# Workstream A: site and launch geometry

Reconstructs the terrain at Malmesbury Abbey to test the precondition for the
whole feasibility hypothesis: that the prevailing wind climbs a slope at the
launch point and so can generate ridge lift.

## Data

AWS Terrain Tiles (terrarium, zoom 14, ~6 m/px) as a keyless Phase-1 stand-in
for Environment Agency LIDAR. Covers a 7 x 7 km box centred on the abbey
(51.5846 N, 2.0997 W).

## Results (metrics.json)

- The abbey sits on a promontory at the confluence of two Avon branches, about
  10 m above the valley floor along the SW-NE section.
- The local slope **faces SW (aspect 230°)**, so a prevailing SW wind blows
  straight up the escarpment. The geometric precondition holds.
- Slope within 400 m of the abbey: mean 5.2°, p90 12.8°, max 28°. The p90 value
  feeds the ridge-lift model in Workstream C.

## Limitations

The 6 m DEM under-resolves the immediate escarpment. The slope it reports is a
floor, not the true launch-edge gradient. Environment Agency LIDAR (≤1 m) in
Phase 2 will sharpen the slope, which directly scales the available ridge lift.
