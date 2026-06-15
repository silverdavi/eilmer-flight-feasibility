# Workstream C: aerodynamics and flight dynamics

Two questions, both answered with deterministic models whose numbers live in
`metrics.json`: what performance a 200 m glide demands, and whether a tailless
configuration can hold control long enough to use it.

## Glide feasibility (Figure 4)

Steady glide with ridge lift over the SW-facing escarpment (slope p90 = 12.83°
from Workstream A). Ridge lift follows the first-order attached-upslope scaling
`w = U sin(slope)` (FAA Soaring Flight Manual; ERAU), ~1.8 m/s at 8 m/s wind, the
same order as a crude glider's sink rate. Range is integrated as
`vx * h / (sink - w)`.

- **Still air demands L/D = 11.1** to cover 200 m from an 18 m tower: sailplane
  class, implausible for a wood-and-cloth wing (panel b, dotted line).
- With ridge lift, the **required glide ratio falls into the crude cambered-wing
  band (L/D 3-7, hang-glider class, sink 0.75-2 m/s) above only 3.6 m/s of SW
  wind**, and reaches L/D 4.8 at 8 m/s. Panel a shows an L/D 5 wing clearing 200 m
  at ~7.5 m/s, inside the favourable wind band from Workstream B.

The flight is feasible only as a wind-and-slope-assisted glide. "Catching the
breeze from the tower" is load-bearing, not decoration.

## The tail verdict (Figure 5)

A tail shifts the neutral point aft by `(a_t/a_w) V_H (1 - de/da) = 0.28 c`, from
0.25 c (wing alone) to 0.53 c. A pilot hanging with wings on hands and feet has a
CG around 0.35-0.55 c, aft of the tailless neutral point, so the tailless craft
is statically unstable across the whole plausible CG range.

We integrate the pitch response (`alpha, q, theta`) to an 8° gust:

- **Without a tail the pitch attitude passes the 60° loss-of-control line 0.74 s
  after the gust** and departs, against a flight lasting ~13 s (panel a). With a
  tail the same gust damps out.
- The divergence is robust (panel b): time-to-double pitch error is 0.1-0.5 s
  everywhere in the plausible CG band, well under the flight time, even when pitch
  inertia is varied 0.5-2x. With a tail there is no divergence across that band.

This is a quantitative vindication of Eilmer's own diagnosis in William: the want
of a tail, not the want of lift, is what put him on the ground. The same tail
diagnosis is independently reported for Ibn Firnas (c. 875), so it is a real
recurring failure mode, not a literary trope.

## Limitations

- Apparatus geometry is unknown; constants (wing area 7 m², AR 4, mass 80 kg,
  inertia 30 kg m², crude-wing L/D band 3-7) are plausible values from the soaring
  and low-Re literature, not fits. Workstream F sweeps them in a Monte Carlo.
- Ridge lift uses the first-order `w = U sin(slope)`; the Phase-2 microscale CFD
  (Workstream B) will replace it with a modelled vertical-velocity field, and the
  coarse DEM's slope is a floor pending LIDAR.
- Stability is the linear short-period approximation with a body-axis pitch model.
  It fixes the sign of stability and the divergence timescale robustly; the full
  nonlinear departure and the lateral (Dutch-roll, spiral) modes are Phase 2.
