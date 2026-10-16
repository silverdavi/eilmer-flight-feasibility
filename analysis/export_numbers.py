"""Write paper_source_iop/numbers.tex: every number quoted in the manuscript.

Reads the workstream metrics.json files and defines one LaTeX macro per value,
so the text, the figures, and the tables share a single source. Run after the
process_* scripts (run_all.sh does this). Never edit numbers.tex by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper_source_iop" / "numbers.tex"


def load(rel):
    return json.loads((ROOT / rel).read_text())


def f(x, nd=1):
    return f"{x:.{nd}f}"


def pct(p, nd=1):
    return f"{100 * p:.{nd}f}"


def main() -> None:
    ter = load("analysis/terrain/metrics.json")
    wx = load("analysis/weather/metrics.json")
    rdg = load("analysis/weather/ridge_metrics.json")
    aero = load("analysis/aero/metrics.json")
    mc = load("analysis/synthesis/metrics.json")
    bio = load("analysis/biomech/metrics.json")
    g, st, dp, site = aero["glide"], aero["stability"], aero["drag_polar"], aero["site"]
    slope_mc = mc["tracks"]["along_slope"]
    into_mc = mc["tracks"]["into_wind"]
    sw = wx["sw_pct_at_or_above_ms"]

    n = {
        # terrain (analysis/terrain/metrics.json)
        "nRelief": f(ter["relief_abbey_above_valley_m"]),
        "nAspect": f(ter["aspect_deg"], 0),
        "nSlopeMean": f(ter["slope_mean_deg"]),
        "nSlopePninety": f(ter["slope_p90_deg"]),
        "nSlopeRadius": f(ter["slope_radius_m"], 0),
        "nLiftIntoWind": f(site["lift_extent_into_wind_m"], 0),
        "nLiftAlongSlope": f(site["lift_extent_along_slope_m"], 0),
        "nContour": f(-site["along_slope_contour_m"]),
        "nValleyDrop": f(site["valley_drop_sw_m"]),
        # weather (analysis/weather/metrics.json)
        "nHours": f"{wx['n_hours']:,}".replace(",", "\\,"),
        "nFavPct": f(wx["favourable_pct_annual"]["mean"]),
        "nFavLo": f(wx["favourable_pct_annual"]["ci95"][0]),
        "nFavHi": f(wx["favourable_pct_annual"]["ci95"][1]),
        "nFavHours": f"{wx['favourable_hours_per_year']['mean']:,.0f}".replace(",", "\\,"),
        "nFavWinter": f(wx["favourable_pct_by_season"]["DJF"]["mean"]),
        "nSWAnyPct": f(wx["sw_sector_any_speed_pct"]),
        "nSWSixPct": f(sw["6"]["mean"]),
        "nSWSixHours": f"{sw['6']['hours_per_year']:.0f}",
        "nSWEightPct": f(sw["8"]["mean"]),
        "nSWEightLo": f(sw["8"]["ci95"][0]),
        "nSWEightHi": f(sw["8"]["ci95"][1]),
        "nSWEightHours": f"{sw['8']['hours_per_year']:.0f}",
        # ridge lift (analysis/weather/ridge_metrics.json)
        "nRidgePeak": f(rdg["max_surface_lift_ms"]),
        "nRidgeWind": f(rdg["U_wind_ms"], 0),
        "nRidgeFormula": f(rdg["slope_formula_lift_ms"]),
        "nSinkBest": f(rdg["sink_best_wing_ms"]),
        "nSinkNominal": f(rdg["sink_nominal_wing_ms"]),
        "nRidgeMatchWind": f(rdg["wind_for_peak_lift_to_match_best_sink_ms"], 0),
        # glide (analysis/aero/metrics.json)
        "nTrimSpeed": f(aero["inputs"]["glide_speed_ms"]),
        "nMass": f(aero["inputs"]["mass_kg"], 0),
        "nArea": f(aero["inputs"]["wing_area_m2"], 0),
        "nCLtrim": f(aero["inputs"]["cl_trim"]),
        "nTower": f(aero["inputs"]["launch_h_m"], 0),
        "nJump": f(aero["inputs"]["jump_speed_ms"], 0),
        "nHeightToTrim": f(g["height_to_trim_speed_still_air_m"]),
        "nLDStillSteady": f(g["ld_needed_still_air_steady"]),
        "nStillRangeBest": f(g["still_air_range_best_m"], 0),
        "nStillRangeSteady": f(g["still_air_range_best_steady_m"], 0),
        "nMaxRangeInto": f(g["max_range_into_wind_m"], 0),
        "nMinWindBest": f(g["min_wind_for_200m_ms"]["along_slope_high"]),
        "nMinWindNominal": f(g["min_wind_for_200m_ms"]["along_slope_nominal"]),
        "nRangeEightBest": f(g["range_at_8ms_along_slope_m"]["high"], 0),
        "nRangeEightNominal": f(g["range_at_8ms_along_slope_m"]["nominal"], 0),
        "nRangeEightIntoBest": f(g["range_at_8ms_into_wind_m"]["high"], 0),
        "nMinWindTowerLo": f(g["min_wind_best_tower15_ms"]),
        "nMinWindTowerHi": f(g["min_wind_best_tower25_ms"]),
        # drag polar
        "nARlo": f(dp["aspect_ratio"][0], 0), "nARhi": f(dp["aspect_ratio"][1], 0),
        "nElo": f(dp["oswald_e"][0]), "nEhi": f(dp["oswald_e"][1]),
        "nCDzlo": f(dp["cd0"][0], 2), "nCDzhi": f(dp["cd0"][1], 2),
        "nLDlo": f(dp["ld_max_band"][0]), "nLDhi": f(dp["ld_max_band"][1]),
        "nLDnom": f(dp["ld_max_nominal"]),
        # stability
        "nNPnotail": f(st["np_notail"], 2), "nNPtail": f(st["np_tail"], 2),
        "nCGlo": f(st["cg_plausible"][0], 2), "nCGhi": f(st["cg_plausible"][1], 2),
        "nCGonset": f(st["cg_divergence_onset"], 2),
        "nTloss": f(st["notail_time_to_control_loss_s"], 2),
        "nTdoubleRep": f(st["notail_time_to_double_s"], 2),
        "nTdoubleFwd": f(st["notail_time_to_double_at_cg_fwd_s"], 2),
        "nTdoubleAft": f(st["notail_time_to_double_at_cg_aft_s"], 2),
        "nTdoubleInLo": f(st["notail_time_to_double_band_s"][0], 2),
        "nTdoubleInHi": f(st["notail_time_to_double_band_s"][1], 2),
        "nFlightTime": f(st["flight_time_s"], 0),
        "nReactLo": f(st["reaction_time_s"][0], 2),
        "nReactHi": f(st["reaction_time_s"][1], 1),
        # Monte Carlo (analysis/synthesis/metrics.json)
        "nSamples": f"{mc['n_samples']:,}".replace(",", "\\,"),
        "nReachSlope": pct(slope_mc["p_reach_200m"][0]),
        "nReachSlopeLo": pct(slope_mc["p_reach_200m"][1]),
        "nReachSlopeHi": pct(slope_mc["p_reach_200m"][2]),
        "nReachSlopeN": f"{slope_mc['n_reach_200m']:,}".replace(",", "\\,"),
        "nReachInto": f"{into_mc['n_reach_200m']}",
        "nReachIntoHi": pct(into_mc["p_reach_200m"][2], 2),
        "nMedRangeSlope": f(slope_mc["median_range_m"], 0),
        "nMedRangeInto": f(into_mc["median_range_m"], 0),
        "nNinetyRangeSlope": f(slope_mc["p90_range_m"], 0),
        "nShortFifty": pct(slope_mc["p_landed_within_50m"], 0),
        "nMedWindReach": f(slope_mc["median_wind_reached_ms"]),
        "nTenWindReach": f(slope_mc["p10_wind_reached_ms"]),
        "nMedLDReach": f(slope_mc["median_ld_reached"]),
        "nMedLDAll": f(slope_mc["median_ld_all"]),
        "nMedFlightReach": f(slope_mc["median_flight_time_reached_s"], 0),
        "nTdoubleMC": f(mc["notail_t2_median_reached_s"], 2),
        "nTdoubleMCpnn": f(mc["notail_t2_p99_reached_s"], 1),
        # biomechanics (analysis/biomech/metrics.json)
        "nTibiaLo": f(bio["leg_fracture_per_leg_kN"][0]),
        "nTibiaHi": f(bio["leg_fracture_per_leg_kN"][1]),
        "nOnsetMid": f(bio["fracture_onset_speed_mid_ms"]),
        "nOnsetLo": f(bio["fracture_onset_speed_range_ms"][0]),
        "nOnsetHi": f(bio["fracture_onset_speed_range_ms"][1]),
        "nCtrlVzMed": f(bio["controlled_vz_median_ms"]),
        "nCtrlVzMax": f(bio["controlled_vz_max_ms"]),
        "nDepVzMed": f(bio["median_departure_vertical_speed_ms"]),
        "nDepAngLo": f(bio["depart_angle_deg"][0], 0),
        "nDepAngHi": f(bio["depart_angle_deg"][1], 0),
        "nVreachLo": f(bio["airspeed_reached_ms"][0]),
        "nVreachHi": f(bio["airspeed_reached_ms"][1]),
        "nPbreakDep": pct(bio["p_legs_break_if_departed"], 0),
        "nDecelG": f(bio["median_departure_decel_g"], 0),
    }
    # worked-exercise answers (Section 6 / Supplementary S4), from the same inputs
    import math
    V = aero["inputs"]["glide_speed_ms"]
    s_p90 = math.sin(math.radians(ter["slope_p90_deg"]))
    for tag, ld in (("Nom", dp["ld_max_nominal"]), ("Hi", dp["ld_max_band"][1])):
        sink = V / math.sqrt(1 + ld**2)
        n[f"nExSink{tag}"] = f(sink)
        n[f"nExUsoar{tag}"] = f(sink / s_p90)
    n["nExWilsonHalf"] = f(100 * (slope_mc["p_reach_200m"][2] - slope_mc["p_reach_200m"][1]) / 2, 2)
    n["nExHeadwind"] = f(V - aero["inputs"]["jump_speed_ms"])
    n["nExVdepFifty"] = f(V * math.sin(math.radians(50)))
    lines = ["% numbers.tex: generated by analysis/export_numbers.py from metrics.json.",
             "% Do not edit by hand; rerun the pipeline.", ""]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in n.items()]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(n)} macros)")


if __name__ == "__main__":
    main()
