"""Pydantic data models shared by ingestion, analysis and the web API.

Conventions
-----------
* ``position_mm`` is the distance (mm) from the cusp apex (the earliest-forming
  dentine) to the midpoint of the sampled increment. Increasing position means
  later-forming tissue, i.e. older age at formation.
* Isotope values are reported in per mil (‰) against the usual standards
  (AIR for δ15N, VPDB for δ13C).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

# Ratio of atomic masses used to convert a weight-% C:N ratio to an atomic ratio.
N_TO_C_MASS = 14.007 / 12.011

ModelName = Literal["logistic", "piecewise", "exponential", "two_phase", "elbow"]
Milestone = Literal["onset", "midpoint", "completion"]


class IsotopeSample(BaseModel):
    """One incremental dentine sample measured by EA-IRMS."""

    model_config = ConfigDict(str_strip_whitespace=True)

    specimen_id: str = Field(min_length=1, description="Unique tooth ID")
    individual_id: str | None = Field(
        default=None, description="Animal ID; teeth sharing it are analysed as one timeline"
    )
    site: str = Field(min_length=1)
    species: str = Field(min_length=1, description="e.g. cattle, pig, horse")
    tooth: str = Field(min_length=1, description="Tooth element, e.g. M1, M2, dp4")
    position_mm: float = Field(ge=0, le=200, description="Distance from cusp apex (mm)")
    position_reference: Literal["apex", "cervix"] = Field(
        default="apex", description="Origin the position was measured from"
    )
    crown_height_mm: float | None = Field(
        default=None, gt=0, le=200, description="Needed to convert cervix-referenced positions"
    )
    position_measured_mm: float | None = Field(
        default=None, description="Position as originally measured (set on conversion)"
    )
    d15N: float = Field(ge=-10, le=30, description="δ15N (‰ AIR)")
    sample_index: int | None = Field(default=None, ge=0)
    d13C: float | None = Field(default=None, ge=-45, le=5, description="δ13C (‰ VPDB)")
    pct_N: float | None = Field(default=None, ge=0, le=100)
    pct_C: float | None = Field(default=None, ge=0, le=100)
    cn_ratio: float | None = Field(default=None, gt=0, le=50, description="Atomic C:N")
    collagen_yield_pct: float | None = Field(default=None, ge=0, le=100)
    period: str | None = None
    notes: str | None = None
    increment_width_mm: float | None = Field(
        default=None, gt=0, le=20, description="Height of the sampled increment (mm)"
    )
    known_weaning_age_months: float | None = Field(
        default=None, ge=0, description="Only for known-age reference animals"
    )
    published_weaning_age_months: float | None = Field(
        default=None, ge=0, description="Weaning age reported in a published study, for comparison"
    )

    @field_validator("species")
    @classmethod
    def _lower_species(cls, value: str) -> str:
        return value.lower()

    @field_validator("position_reference", mode="before")
    @classmethod
    def _lower_reference(cls, value):
        return value.strip().lower() if isinstance(value, str) and value.strip() else "apex"

    @field_validator("period", "notes", "individual_id", mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _to_apex(self) -> "IsotopeSample":
        """Convert cervix-referenced positions to distance from the apex (idempotent)."""
        if self.position_reference == "cervix":
            if self.crown_height_mm is None:
                raise ValueError("crown_height_mm is required when position_reference is 'cervix'")
            if self.position_mm > self.crown_height_mm:
                raise ValueError("position from the cervix exceeds crown_height_mm")
            self.position_measured_mm = self.position_mm
            self.position_mm = round(self.crown_height_mm - self.position_mm, 4)
            self.position_reference = "apex"
            self.notes = ((self.notes + "; ") if self.notes else "") + "position converted from cervix"
        return self

    @model_validator(mode="after")
    def _derive_cn(self) -> "IsotopeSample":
        if self.cn_ratio is None and self.pct_C and self.pct_N:
            self.cn_ratio = round(self.pct_C / self.pct_N * N_TO_C_MASS, 3)
        return self


class QCThresholds(BaseModel):
    """Collagen quality criteria. Samples outside these ranges are flagged."""

    cn_min: float = 2.9
    cn_max: float = 3.6
    pct_C_min: float = 13.0
    pct_N_min: float = 4.8
    collagen_yield_min: float = 1.0
    exclude_failed: bool = True


class GrowthKnot(BaseModel):
    position_mm: float = Field(ge=0)
    age_months: float = Field(ge=-12)


class GrowthTable(BaseModel):
    """Maps position along a tooth to age at formation (piecewise linear)."""

    species: str
    tooth: str
    label: str
    knots: list[GrowthKnot] = Field(min_length=2)
    age_uncertainty_months: float = Field(default=0.0, ge=0)
    source: str = ""
    placeholder: bool = False
    tbd_note: str | None = None

    @model_validator(mode="after")
    def _monotonic(self) -> "GrowthTable":
        pos = [k.position_mm for k in self.knots]
        ages = [k.age_months for k in self.knots]
        if any(b <= a for a, b in zip(pos, pos[1:])):
            raise ValueError("growth-table positions must be strictly increasing")
        if any(b < a for a, b in zip(ages, ages[1:])):
            raise ValueError("growth-table ages must be non-decreasing")
        return self

    @property
    def key(self) -> str:
        return f"{self.species}:{self.tooth}"


class LinearGrowthOverride(BaseModel):
    """Simple user-supplied age model: age = initiation + position / rate."""

    initiation_age_months: float = Field(ge=-12)
    extension_rate_mm_per_month: float = Field(gt=0)


class AdultBaseline(BaseModel):
    """δ15N of adult females (the mothers' population), after WARN's maternal baseline."""

    mean: float = Field(ge=-10, le=30)
    sd: float = Field(default=0.5, gt=0)


class AnalysisOptions(BaseModel):
    models: list[ModelName] = Field(
        default_factory=lambda: ["logistic", "piecewise", "exponential", "two_phase", "elbow"]
    )
    # Fraction of the nursing-to-adult δ15N drop treated as "begun" / "complete"
    # for smooth models (0.05 => onset at 5 % of drop, completion at 95 %).
    transition_threshold: float = Field(default=0.05, gt=0, lt=0.5)
    reported_milestone: Milestone = "completion"
    analytical_sd_permil: float | None = Field(default=None, gt=0)
    min_weaning_drop_permil: float = Field(default=1.0, ge=0)
    monte_carlo_draws: int = Field(default=1000, ge=0, le=20000)
    random_seed: int | None = 42
    qc: QCThresholds = Field(default_factory=QCThresholds)
    # Custom linear age models keyed by "species:tooth" (e.g. "cattle:M2"); these
    # take precedence over the bundled growth tables.
    growth_overrides: dict[str, LinearGrowthOverride] = Field(default_factory=dict)

    # Time averaging (after MDSS / Tsutaya 2020): each sample integrates dentine
    # formed over an age window rather than at a single instant.
    time_averaging: bool = False
    increment_width_mm: float = Field(default=1.0, gt=0, le=20)
    growth_layer_offset_mm: float = Field(default=0.0, ge=0, le=50)
    # Relative contribution of the latest-formed (innermost) dentine in a section;
    # 1 = uniform, < 1 = linearly less volume towards the pulp (cf. MDSS volumes).
    inner_dentine_weight: float = Field(default=1.0, gt=0, le=1)
    # Seasonality: optional annual sinusoid added to every parametric curve.
    seasonal_term: bool = False
    season_period_months: float = Field(default=12.0, gt=0)
    # Uncertainty: parameter covariance (fast) or residual bootstrap (robust).
    uncertainty: Literal["covariance", "bootstrap"] = "covariance"
    bootstrap_draws: int = Field(default=200, ge=0, le=5000)
    # Adult-female δ15N baselines keyed "site:species" (or just "species").
    adult_baselines: dict[str, AdultBaseline] = Field(default_factory=dict)
    # Extra or edited growth tables supplied with this analysis (take precedence).
    growth_tables: list["GrowthTable"] = Field(default_factory=list)
    constrain_adult_plateau: bool = False
    # Elbow method (after WEAN): normalise both axes before measuring distance.
    elbow_normalise: bool = True

    def override_for(self, species: str, tooth: str) -> LinearGrowthOverride | None:
        wanted = f"{species}:{tooth}".lower()
        return next((v for k, v in self.growth_overrides.items() if k.lower() == wanted), None)

    def baseline_for(self, site: str, species: str) -> AdultBaseline | None:
        keys = {k.lower(): v for k, v in self.adult_baselines.items()}
        return keys.get(f"{site}:{species}".lower()) or keys.get(species.lower())


class ValueWithCI(BaseModel):
    estimate: float | None
    ci_low: float | None = None
    ci_high: float | None = None


class FitResult(BaseModel):
    model: ModelName
    label: str
    converged: bool
    message: str = ""
    params: dict[str, float] = Field(default_factory=dict)
    param_se: dict[str, float | None] = Field(default_factory=dict)
    nursing_d15N: float | None = None
    adult_d15N: float | None = None
    drop_permil: float | None = None
    enrichment_permil: float | None = None
    extra: dict[str, float] = Field(default_factory=dict)
    onset: ValueWithCI | None = None
    midpoint: ValueWithCI | None = None
    completion: ValueWithCI | None = None
    rmse: float | None = None
    r2: float | None = None
    aicc: float | None = None
    delta_aicc: float | None = None
    akaike_weight: float | None = None
    warnings: list[str] = Field(default_factory=list)
    curve_age: list[float] = Field(default_factory=list)
    curve_d15N: list[float] = Field(default_factory=list)
    # Milestone draws (after age-model error) kept for model averaging; not serialised.
    _draws: dict = PrivateAttr(default_factory=dict)


class SamplePoint(BaseModel):
    position_mm: float
    age_months: float
    d15N: float
    d13C: float | None = None
    tooth: str | None = None
    age_min: float | None = None
    age_max: float | None = None
    extrapolated: bool = False
    qc_flags: list[str] = Field(default_factory=list)
    used_in_fit: bool = True


class SpecimenResult(BaseModel):
    specimen_id: str
    site: str
    species: str
    tooth: str
    period: str | None = None
    growth_table: str
    growth_placeholder: bool
    points: list[SamplePoint]
    fits: list[FitResult]
    best_model: ModelName | None = None
    model_average: dict[str, ValueWithCI] = Field(default_factory=dict)
    diagnostics: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    known_weaning_age_months: float | None = None
    published_weaning_age_months: float | None = None
    adult_baseline: AdultBaseline | None = None


class EstimateRow(BaseModel):
    """Flat summary of one model's estimate for one specimen (used for aggregation)."""

    specimen_id: str
    site: str
    species: str
    period: str | None = None
    model: str  # a ModelName, or "average" for the Akaike-weighted average
    is_best: bool = False
    onset: float | None = None
    midpoint: float | None = None
    completion: float | None = None
    completion_ci_low: float | None = None
    completion_ci_high: float | None = None
    known_weaning_age_months: float | None = None
    published_weaning_age_months: float | None = None
    akaike_weight: float | None = None
