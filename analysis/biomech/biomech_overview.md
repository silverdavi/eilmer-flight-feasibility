# Workstream E — Impact biomechanics (the broken-legs constraint)

**Question.** William of Malmesbury records that Eilmer broke both legs and was
lame thereafter, but survived. Treat that as a data point: what arrival speed and
attitude produce *bilateral leg fracture that is survivable*, and is it consistent
with a controlled landing or with an uncontrolled departure?

## Model

A feet-first impact decelerates the body over a stopping distance `d` (leg flexion
plus ground give). Average force is energy over distance:

```
F_total = m v^2 / (2 d)      per leg  F_total / 2
```

The tibia fractures under axial and combined loading at **7.5–11.3 kN per leg**
(Salzar et al. 2014; Abidin et al. 2026). This sets a **fracture-onset vertical
impact speed**:

```
v* = sqrt( 2 d F_total / m )
```

- `m = 80 kg`, `d ∈ {10, 20, 35} cm`, two legs sharing the load.
- Flared touchdown: vertical speed ≈ sink rate, **1–3 m/s**.
- Uncontrolled departure: arrives near flying speed, vertical component
  `V·sin θ` with `V = 11–16 m/s` and impact angle `θ = 35–70°`.

## Result (`metrics.json`)

| Quantity | Value |
|---|---|
| Fracture-onset speed (d = 20 cm) | **9.7 m/s** |
| Fracture-onset range (d = 35→10 cm) | 7.5–11.5 m/s |
| Median departure vertical speed | 10.5 m/s |
| P(legs break \| departed), d = 20 cm | **0.66** |
| P(legs break \| flared) | 0.00 |
| Median departure deceleration | ~28 g → survivable feet-first |

## Reading

A **flared landing cannot break the legs** (1–3 m/s sits far below the 7.5–11.5 m/s
onset). An **uncontrolled departure** arrives at ~10 m/s vertical, which breaks both
tibiae across the plausible range of ground give, yet at ~28 g over the legs it is a
*survivable* feet-first hit — not the >100 g fatal regime. So the broken legs are
not incidental: they are positive evidence that Eilmer arrived **out of control**,
which is exactly the failure mode the missing tail predicts (Workstreams C, F). The
injury report and the aerodynamics tell the same story.

## Limitations

- Average-force (energy/distance) model, not a peak-load transient; real peak forces
  are higher, so onset speeds are conservative upper bounds.
- Axial tibia tolerance only; bending (312–447 N·m) and combined loading would lower
  the threshold further.
- Ground give and posture (`d`, θ) are the dominant unknowns and are swept, not fit.
- Figure 7: panel **a** force–speed curves with the tibia band; panel **b** flared vs
  departure impact-speed distributions against the fracture-onset band.
