# Workstream B: wind feasibility

Quantifies how often Malmesbury offered wind able to support the flight. We
cannot know the weather of an unknown day c. 1010-1040, so we report a
climatological probability and defend its transfer back to the Medieval Climate
Anomaly.

## Data

ERA5 hourly 10 m wind via the keyless Open-Meteo archive, 2004-2023 (175,320
hours) at the abbey. Phase-1 stand-in for a direct CDS ERA5 pull and NOAA-CIRES
20CR.

## Results (metrics.json)

Favourable launch = wind from the SW sector (191-259°, climbing the SW-facing
escarpment from Workstream A) at 5-12 m/s (usable ridge-soaring band).

- **15.6% of all hours are favourable (95% CI 14.3-17.0 across years)**, about
  1,370 hours per year (range 689-1,869). Eilmer could choose his day.
- SW-sector wind of any speed occurs 34% of the time.
- Favourability peaks in winter (DJF 21.1%) and is lowest in spring (12.1%).

## Ridge-lift field (Figure 3)

A first-order linear orographic model, `w = U dh/dx exp(-k z)`, over the real
SW-NE terrain section gives the vertical-velocity field at the launch point. It is
the Phase-1 stand-in for the LES / WAsP solve and is consistent by construction
with the `w = U sin(slope)` scaling in Workstream C.

- An 8 m/s SW wind produces **~1.5 m/s of lift on the windward face just SW of
  the abbey**, exceeding a crude glider's optimistic sink (0.75-1 m/s).
- The soarable working band is **~38 m deep** at a 1 m/s sink.

This is marginal, and honestly so: the coarse 6 m DEM under-resolves the
escarpment, so the modelled slope (and lift) is a floor. LIDAR + LES in Phase 2
should raise both. The figure's role is to show the mechanism is present and of
the right order, not to settle the margin.

## Stationarity to the MCA

NAO reconstructions (Trouet et al. 2009; Ortega et al. 2015) describe the MCA as
persistently positive-NAO, i.e. stronger and more frequent westerlies. Modern
reanalysis is therefore a conservative proxy: conditions were plausibly at least
as favourable in Eilmer's day.

## Limitations

The 5-12 m/s band is a generic soaring window, not yet tied to the apparatus
sink rate. Phase-2 microscale CFD will convert the synoptic wind into a modelled
ridge-lift field at the launch edge and replace the band with a lift threshold.
