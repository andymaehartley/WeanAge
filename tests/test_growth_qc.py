import numpy as np

from weanage.config import find_growth_table, growth_tables, tbd_items
from weanage.growth import position_to_age
from weanage.qc import passes_qc, qc_flags
from weanage.schema import GrowthTable, IsotopeSample, LinearGrowthOverride, QCThresholds


def test_interpolation_and_extrapolation():
    table = GrowthTable(species="x", tooth="M1", label="x",
                        knots=[{"position_mm": 0, "age_months": 0}, {"position_mm": 10, "age_months": 5}])
    ages, extra = position_to_age([0, 5, 10, 12], table)
    np.testing.assert_allclose(ages, [0, 2.5, 5, 6])
    assert extra.tolist() == [False, False, False, True]


def test_linear_override_wins():
    table = find_growth_table("cattle", "M2")
    ages, _ = position_to_age([0, 6], table, LinearGrowthOverride(initiation_age_months=2, extension_rate_mm_per_month=3))
    np.testing.assert_allclose(ages, [2, 4])


def test_placeholders_are_registered_as_tbd():
    ids = {i["id"] for i in tbd_items()}
    for table in growth_tables().values():
        if table.placeholder:
            assert f"growth:{table.key}" in ids


def test_qc_flags():
    qc = QCThresholds()
    base = dict(specimen_id="a", site="s", species="cattle", tooth="M2", position_mm=0, d15N=7)
    assert passes_qc(qc_flags(IsotopeSample(**base, cn_ratio=3.2, pct_C=40, pct_N=14), qc))
    bad = qc_flags(IsotopeSample(**base, cn_ratio=4.0), qc)
    assert "cn_out_of_range" in bad and not passes_qc(bad)
    assert qc_flags(IsotopeSample(**base), qc) == ["qc_not_assessed"]
