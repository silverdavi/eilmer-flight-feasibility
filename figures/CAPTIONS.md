# Figure captions

Single source of truth for figure captions. One entry per figure, each written to
stand alone under the figure. Manuscript numbers are below; the image **file names
retain their build numbers** (`fig1_site`, ...), noted in each entry. Keep these in
sync with the workstream overview docs in `analysis/` and with the LaTeX captions in
`paper_source/sections/`. Every number traces to a `metrics.json`.

Slate: seven main figures (1--7) plus one supplementary figure (S1, ridge lift) and
one supplementary table (S1, Monte Carlo priors). The ridge-lift field is
supplementary because the first-order model over a smoothed 6 m DEM is a lower
bound; the main text carries only its magnitude.

---

## Figure 1 — Eilmer's apparatus and the flight it could fly
*File: `figures/apparatus_flight.png` (lead figure)*

**Figure 1 | Eilmer's apparatus and the flight it could fly.**
**(a)** A to-scale reconstruction of the apparatus implied by the glide and
stability models: a cambered cloth-membrane wing of about 7 m² and 5.3 m span
(aspect ratio 4) on a willow frame, the pilot prone with wings fixed to the hands
and feet and, as William of Malmesbury records, no tail.
**(b)** Launch geometry on the abbey promontory, with the southwest ground track of
the glide over a contour map of the escarpment, from the tower to an impact about a
furlong away.
**(c)** The flight in profile, apparatus enlarged for clarity: a wind-and-slope
assisted glide with a tail (blue) against the tailless case (red), which loses pitch
control and strikes the ground at about 39° and 19 m s⁻¹. The reconstruction is
illustrative and consistent with the project models, not a literal depiction.

---

## Figure 2 — Site and launch geometry
*File: `figures/fig1_site.png` · Workstream A (terrain)*

**Figure 2 | Site and launch geometry at Malmesbury Abbey.**
**(a)** Hillshaded terrain (AWS Terrain Tiles, about 6 m posting) with the abbey on
a promontory above the confluence of two Avon branches; the SW–NE line marks the
section in (b).
**(b)** Elevation along the section. The abbey stands 10.2 m above the valley floor
on a SW-facing slope (aspect 230°; slope within 400 m: mean 5.2°, p90 12.8°). A
prevailing southwest wind blows directly up the escarpment, which is the geometric
precondition for ridge lift. The 6 m DEM under-resolves the launch edge, so the
reported slope is a lower bound pending LIDAR.

---

## Figure 3 — Wind feasibility
*File: `figures/fig2_wind.png` · Workstream B (weather)*

**Figure 3 | Favourable launch winds are common.**
**(a)** Wind rose of ERA5 hourly 10 m wind at the abbey, 2004–2023 (175,320 h).
**(b)** Fraction of hours offering a favourable launch, defined as the SW sector
(191–259°) at 5–12 m s⁻¹, annually and by season, with 95% confidence intervals
across the 20 years. Favourable conditions occur in 15.6% of hours (95% CI
14.3–17.0), about 1,370 h per year, peaking in winter (21.1%). Eilmer could choose
his day, and medieval NAO reconstructions give no sign of weaker-than-modern
westerlies, so modern reanalysis is a reasonable, probably conservative proxy for
his epoch.

---

## Figure 4 — Glide feasibility
*File: `figures/fig4_glide_envelope.png` · Workstream C (aero)*

**Figure 4 | A 200 m glide needs wind and slope.**
**(a)** Range of an L/D 5 cambered wing launched from an 18 m tower as a function of
southwest wind speed; 200 m is reached at about 7.5 m s⁻¹, inside the favourable
band of Figure 3.
**(b)** Glide ratio required to cover 200 m versus wind speed. Still air demands L/D
11.1 (sailplane class, dotted line), implausible for a wood-and-cloth wing. With
ridge lift the requirement falls into the crude cambered-wing band (L/D 3–7,
hang-glider class) above 3.6 m s⁻¹ of wind, reaching L/D 4.8 at 8 m s⁻¹. The launch
breeze sets whether the glide reaches 200 m.

---

## Figure 5 — Pitch stability and the tail
*File: `figures/fig5_stability.png` · Workstream C (aero)*

**Figure 5 | The tailless craft cannot hold pitch.**
**(a)** Pitch-attitude response to an 8° gust. Without a tail (red) the attitude
crosses the 60° loss-of-control line 0.74 s after the gust and departs, against a
flight lasting 13.3 s; with a tail (blue) the same gust damps out.
**(b)** Time to double the pitch error across the plausible CG band: 0.1–0.5 s
everywhere for the tailless craft, even with pitch inertia varied 0.5–2×, far
shorter than the flight, and no divergence with a tail. A tail shifts the neutral
point from 0.25\(c\) to 0.53\(c\), aft of a hanging pilot's CG (0.35–0.55\(c\)),
which is what makes the tailless configuration statically unstable.

---

## Figure 6 — Feasibility envelope (Monte Carlo)
*File: `figures/fig6_montecarlo.png` · Workstream F (synthesis)*

**Figure 6 | Feasibility envelope over the unknown apparatus and day.**
40,000 Monte Carlo samples drawing apparatus and launch parameters from plausible
ranges, with launch wind drawn from the actual ERA5 SW-sector launchable speeds.
**(a)** 27% of worlds reach 200 m (95% CI 26–27; median range 147 m).
**(b)** Among those that reach 200 m, the tail decides the outcome through a
timescale mismatch: tailless pitch error doubles in a median 0.27 s (p99 1.6 s),
with control lost after about 3 m, against a flight that must stay controlled for a
median 20 s, roughly 75× too fast to recover, while tailed configurations never
diverge. The model reproduces the account: he covered the distance, then lost
control.

---

## Figure 7 — Impact biomechanics
*File: `figures/fig7_biomech.png` · Workstream E (biomech)*

**Figure 7 | Broken legs as evidence of an out-of-control arrival.**
**(a)** Average feet-first impact force per leg versus vertical impact speed for
ground-give distances \(d = 10\text{–}35\) cm, against the axial tibia fracture band
(7.5–11.3 kN per leg). Fracture onset is about 9.7 m s⁻¹ (range 7.5–11.5).
**(b)** Vertical impact-speed distributions for a flared touchdown (sink rate,
1–3 m s⁻¹) versus an uncontrolled departure (\(V\sin\theta\), \(V = 11\text{–}16\)
m s⁻¹, \(\theta = 35\text{–}70°\)). A flared landing cannot break the legs; a
departure breaks both tibiae with probability 0.66 yet, at about 28 g over the legs,
remains survivable. The injury is positive evidence that Eilmer arrived out of
control, the failure mode the missing tail predicts in Figures 5 and 6.

---

# Supplementary figures

## Figure S1 — Modelled ridge lift
*File: `figures/fig3_ridge_lift.png` · Workstream B (weather)*

**Figure S1 | Ridge lift over the escarpment matches a crude glider's sink.**
A first-order linear orographic model (\(w = U\,\mathrm{d}h/\mathrm{d}x\,e^{-kz}\))
over the real SW–NE terrain section.
**(a)** Vertical-velocity field and streamlines for an 8 m s⁻¹ southwest wind.
**(b)** Lift versus height above the windward face. Peak lift just southwest of the
abbey is about 1.5 m s⁻¹, above a crude glider's optimistic sink of 0.75–1 m s⁻¹,
with a soarable band about 38 m deep. The mechanism is present and of the right
order. The coarse DEM makes the modelled slope, and hence the lift, a lower bound.
