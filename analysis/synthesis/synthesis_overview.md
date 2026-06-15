# Workstream F: Monte Carlo feasibility envelope

Turns the point results of Workstreams B and C into probabilities over the
unknown apparatus and launch day. 40,000 samples (seed 42) draw wing area, mass,
trim CL, glide ratio, tower height, escarpment slope, ridge-lift efficiency, CG,
aspect ratio, and tail size from plausible ranges (see paper Methods and Table S1). Launch
wind is drawn from the actual ERA5 SW-sector launchable speeds, so this inherits
Workstream B rather than assuming a wind.

Each world is scored on two axes: does the glide cover 200 m, and does it stay
controlled (time-to-double pitch error longer than the flight), for a tailless
and a tailed configuration.

## Results (metrics.json, Figure 6)

- **27% of plausible worlds reach 200 m** (95% CI 26-27), median range 147 m. The
  typical draw falls short, but a flight of a furlong is far from rare, and the
  realised event had a chosen day and presumably a sound build, i.e. the upper
  part of this distribution.
- **The reached quarter flips entirely on the tail.** Of worlds that reach 200 m,
  every tailless one departs before landing; every tailed one stays controlled.
  This reproduces the account: he covered the distance, then lost control.
- **The flip is a timescale mismatch (Fig 6b).** A tailless craft doubles its
  pitch error in a median 0.27 s (p99 1.6 s), i.e. control is gone after ~3 m,
  while the flight must stay controlled for a median ~20 s — divergence is ~75x
  too fast to fly out. With a tail, every reaching configuration is statically
  stable and never diverges. Panel b plots these two timescales directly rather
  than the redundant reach split, which is identical by construction (panel a).

## Why the tail result is binary, and robust

A hanging pilot's CG (0.35-0.55 c) is always aft of the tailless neutral point
(0.25 c), so the tailless craft is always statically unstable, and the divergence
is fast (sub-second) relative to the flight. A tail adds both an aft neutral-point
shift and strong pitch damping; even when the CG sits aft of the tailed neutral
point, the damping keeps the growth slow enough to remain recoverable within the
flight. Varying tail size (neutral-point shift 0.18-0.32 c) does not change this.

## Limitations

- The departure criterion is linear (time-to-double vs flight time) and uses a
  single gust; a gust-amplitude sweep and the lateral (Dutch-roll, spiral) modes
  would soften the binary and belong in a Phase-2 6-DOF model.
- Parameter ranges are uniform plausible priors, not measured distributions.
- Wind is modern ERA5; a positive-NAO MCA uplift (Trouet 2009) would raise the
  reach fraction and is reported separately as a sensitivity, not baked in here.
