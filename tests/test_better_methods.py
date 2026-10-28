"""Dental transition analysis, concentration-dependent mixing, origins, the infant correction and other wear stages."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from weanage import config
from weanage.dental_age import AGE_GRID, analyze_dental, ingest_dental_dataframe, stage_likelihood
from weanage.killoff import analyze_killoff
from weanage.lifetable import analyze_lifetable
from weanage.mixing import analyze_mixing
from weanage.mobility import analyze_mobility, ingest_mobility_dataframe
from weanage.schema import (
    DentalOptions,
    DietSource,
    KilloffOptions,
    KilloffSample,
    LifeSample,
    LifeTableOptions,
    MixingOptions,
    MixingSample,
    MobilityOptions,
    OriginRegion,
)

TEST_DATA = Path(__file__).parent / "data"
EXAMPLES = config.DATA_DIR / "examples"


def test_stage_likelihoods_cover_the_ages():
    table = config.dental_stages()
    total = sum(stage_likelihood("M1", s, table) for s in table["stages"])
    after = AGE_GRID > 12  # once the tooth has certainly begun, every age is in exactly one stage
    assert np.allclose(total[after], 1, atol=1e-3)


@pytest.mark.parametrize("teeth", ["independent", "dependent"])
def test_transition_analysis_recovers_the_example(teeth):
    df = pd.read_csv(EXAMPLES / "synthetic_dental_example.csv")
    truth = df.groupby("specimen_id").notes.first().str.extract(r"true age ([\d.]+)")[0].astype(float)
    results = analyze_dental(ingest_dental_dataframe(df)["samples"], DentalOptions(teeth=teeth))["results"]
    errors = [r["estimate_months"] - truth[r["specimen_id"]] for r in results]
    inside = [r["age_min_months"] <= truth[r["specimen_id"]] <= r["age_max_months"] for r in results]
    assert np.mean(np.abs(errors)) < 6 and np.mean(inside) >= 0.9
    assert all(r["method"] == "transition" for r in results)


def test_concentration_dependence_shifts_the_shares():
    foods = [DietSource(name="plants", d13C=-25, d13C_sd=0.3, d15N=3, d15N_sd=0.3, conc_C=40, conc_N=2),
             DietSource(name="meat", d13C=-21, d13C_sd=0.3, d15N=7, d15N_sd=0.3, conc_C=50, conc_N=14)]
    person = [MixingSample(specimen_id="a", site="s", species="human", d13C=-22, d15N=9)]

    def meat(sources):
        options = MixingOptions(sources=sources, offset_d13C=1, offset_d13C_sd=0.1, offset_d15N=4, offset_d15N_sd=0.1)
        return analyze_mixing(person, options)["results"][0]["shares"]["meat"]["estimate"]

    plain = [f.model_copy(update={"conc_C": None, "conc_N": None}) for f in foods]
    assert abs(meat(plain) - 0.5) < 0.05
    assert meat(foods) < 0.4  # meat is rich in nitrogen, so less of it explains the same δ15N
    favoured = [foods[0], foods[1].model_copy(update={"prior": 20})]
    assert meat(favoured) > meat(foods)  # a prior favouring meat moves the shares towards it


def test_origins_rank_the_places():
    samples = ingest_mobility_dataframe(pd.read_csv(TEST_DATA / "synthetic_mobility_example.csv"))["samples"]
    places = [OriginRegion(name="old rocks, colder", sr87_86=0.7125, d18O_dw=-10),
              OriginRegion(name="chalk, warmer", sr87_86=0.708, d18O_dw=-6)]
    out = analyze_mobility(samples, MobilityOptions(regions=places))
    incomers = [r for r in out["results"] if r["non_local"]]
    assert incomers and all(r["origins"]["candidates"][0]["region"] == "old rocks, colder" for r in incomers)
    assert all(r["origins"] is None for r in out["results"] if not r["non_local"])


def test_infant_correction_reaches_the_target_share():
    skeletons = [LifeSample(specimen_id=str(i), site="S", species="human", age_min_years=a, age_max_years=a + 10)
                 for i, a in enumerate([20, 30, 40, 50] * 10)]
    out = analyze_lifetable(skeletons, LifeTableOptions(expected_infant_share=0.3, bootstrap_draws=0, siler=False))
    corrected = out["results"][0]["corrected"]
    assert corrected["summary"]["infant_share"] == pytest.approx(0.3)
    assert corrected["added_infants"] == pytest.approx(0.3 * 40 / 0.7)
    assert corrected["summary"]["e0"] < out["results"][0]["summary"]["e0"]["estimate"]


def test_other_wear_stage_systems():
    mandibles = [KilloffSample(specimen_id=str(i), site="S", species="cattle", wear_stage=w)
                 for i, w in enumerate(["B", "C", "C/D", "D"] * 10)]
    table = {"B": (1, 8), "C": (8, 18), "D": (18, 30)}
    out = analyze_killoff(mandibles, KilloffOptions(stage_ages=table, class_bounds_months=[0, 1, 8, 18, 30, 48]))
    assert out["results"][0]["n"] == 40
    with pytest.raises(ValueError, match="stage table"):
        analyze_killoff(mandibles, KilloffOptions())
