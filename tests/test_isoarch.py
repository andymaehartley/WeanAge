"""Reading sequential dentine series from an IsoArcH export."""

import pandas as pd

from weanage.isoarch import species_name, summary, to_weanage, zone_key


def make_export(path):
    """A tiny IsoArcH-style workbook: one cow, an M2 sampled in 6 zones a-f."""
    zones = list("abcdef")
    sheets = {
        "Organic measures": pd.DataFrame({
            "Sample identifier": ["S1"] * 6, "Dataset DOI": ["10.1/x"] * 6, "Sampled zone identifier": zones,
            "Tooth fraction": ["dentine"] * 6, "δ13C (‰vpdb)": [-21.0] * 6, "δ15N (‰air)": [5, 5.2, 6, 7, 8, 8.1]}),
        "Samples": pd.DataFrame({"Sample identifier": ["S1"], "Material identifier": ["M1"],
                                 "Tooth category": ["molar"], "Tooth numbering": [2]}),
        "Materials": pd.DataFrame({
            "Material identifier": ["M1"], "Location name": ["Site X"], "Original material identifier": ["COW1"],
            "Reported biological identification": ["Bos taurus"], "Short references": ["Author (2020)"],
            "Relative dating - lower limit": [1000], "Relative dating - upper limit": [1100],
            "Archaeological period": [None]}),
        "Datasets": pd.DataFrame({"Dataset DOI": ["10.1/x"], "Dataset license": ["CC-BY-4.0"]}),
    }
    with pd.ExcelWriter(path) as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)


def test_names_and_zone_order():
    assert species_name("Bos taurus") == "cattle" and species_name("Ovis aries/Capra_x000D_\nhircus") == "sheep/goat"
    assert sorted(["b", "aa", "a", "z"], key=zone_key) == ["a", "b", "z", "aa"]
    assert sorted(["10", "2", "1"], key=zone_key) == ["1", "2", "10"]


def test_conversion(tmp_path):
    path = tmp_path / "export.xlsx"
    make_export(path)
    assert summary(path).iloc[0]["slices"] == 6
    rows = to_weanage(path, ["Site X"], ["cattle"])
    assert list(rows["tooth"].unique()) == ["M2"] and rows["period"].iloc[0] == "AD 1000-1100"
    assert rows["position_mm"].is_monotonic_decreasing  # zone "a" at the cervix: furthest from the cusp
    assert rows["position_mm"].max() < 45 and "ASSUMED" in rows["notes"].iloc[0]
    crown = to_weanage(path, ["Site X"], zone_order="crown_first", spacing_mm=1.0)
    assert list(crown["position_mm"]) == [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
