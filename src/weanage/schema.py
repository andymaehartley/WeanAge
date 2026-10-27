"""The shapes of the data we accept, checked automatically by pydantic.

Positions are in mm from the cusp apex (the tip of the crown, where dentine forms
first). Isotope values are in per mil (‰).
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ModelName = Literal["logistic", "piecewise", "exponential", "two_phase", "elbow"]
MODEL_NAMES: list[ModelName] = ["logistic", "piecewise", "exponential", "two_phase", "elbow"]


class Sample(BaseModel):
    """What every sample has, and how spreadsheet cells are read."""

    specimen_id: str = Field(min_length=1)
    site: str = Field(min_length=1)
    species: str = Field(min_length=1)
    period: str | None = None
    notes: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def blank_is_missing(cls, value):
        # Spreadsheets often contain "" or spaces for "no value".
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("species", mode="before")
    @classmethod
    def lower_case(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class CollagenSample(Sample):
    """A collagen measurement, from a tooth slice or a bone."""

    d15N: float = Field(ge=-10, le=30)
    d13C: float | None = Field(default=None, ge=-45, le=5)
    pct_C: float | None = Field(default=None, ge=0, le=100)
    pct_N: float | None = Field(default=None, ge=0, le=100)
    cn_ratio: float | None = Field(default=None, gt=0, le=50)
    collagen_yield_pct: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def atomic_cn(self):
        if self.cn_ratio is None and self.pct_C and self.pct_N:
            self.cn_ratio = round(self.pct_C / self.pct_N * 14.007 / 12.011, 3)
        return self


class IsotopeSample(CollagenSample):
    """One slice of dentine measured in the lab. specimen_id is one tooth."""

    individual_id: str | None = None  # teeth with the same animal ID are joined
    tooth: str = Field(min_length=1)
    position_mm: float = Field(ge=0, le=200)
    position_reference: Literal["apex", "cervix"] | None = "apex"
    crown_height_mm: float | None = Field(default=None, gt=0, le=200)
    position_measured_mm: float | None = None  # original value if we converted it
    increment_width_mm: float | None = Field(default=None, gt=0, le=20)
    sample_index: int | None = Field(default=None, ge=0)
    known_weaning_age_months: float | None = Field(default=None, ge=0)
    published_weaning_age_months: float | None = Field(default=None, ge=0)

    @field_validator("position_reference", mode="before")
    @classmethod
    def lower_reference(cls, value):
        return value.strip().lower() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def tidy(self):
        self.position_reference = self.position_reference or "apex"
        # Convert "measured from the cervix" into "measured from the apex" (only once).
        if self.position_reference == "cervix":
            if self.crown_height_mm is None:
                raise ValueError("crown_height_mm is needed when position_reference is 'cervix'")
            if self.position_mm > self.crown_height_mm:
                raise ValueError("position from the cervix is larger than crown_height_mm")
            self.position_measured_mm = self.position_mm
            self.position_mm = round(self.crown_height_mm - self.position_mm, 4)
            self.position_reference = "apex"
            self.notes = (self.notes + "; " if self.notes else "") + "position converted from cervix"
        return self


class QCThresholds(BaseModel):
    """Collagen quality limits; samples outside them are flagged."""

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
    """Points that turn a position on the tooth into an age (straight lines between them)."""

    species: str
    tooth: str
    label: str
    knots: list[GrowthKnot] = Field(min_length=2)
    age_uncertainty_months: float = Field(default=0.0, ge=0)
    source: str = ""
    placeholder: bool = False
    tbd_note: str | None = None

    @field_validator("species")
    @classmethod
    def lower_case(cls, value):
        return value.strip().lower()

    @model_validator(mode="after")
    def check_order(self):
        for a, b in zip(self.knots, self.knots[1:]):
            if b.position_mm <= a.position_mm:
                raise ValueError("growth-table positions must increase")
            if b.age_months < a.age_months:
                raise ValueError("growth-table ages must not decrease")
        return self

    @property
    def key(self):
        return f"{self.species}:{self.tooth}"


class LinearGrowthOverride(BaseModel):
    """A simple age model: age = initiation age + position / growth rate."""

    initiation_age_months: float = Field(ge=-12)
    extension_rate_mm_per_month: float = Field(gt=0)


class AdultBaseline(BaseModel):
    """δ15N of adult females (the mothers), as used by WARN."""

    mean: float = Field(ge=-10, le=30)
    sd: float = Field(default=0.5, gt=0)


class AnalysisOptions(BaseModel):
    """Every setting of an analysis. Comments say what each one does."""

    models: list[ModelName] = MODEL_NAMES
    reported_milestone: Literal["onset", "midpoint", "completion"] = "midpoint"
    transition_threshold: float = Field(default=0.05, gt=0, lt=0.5)  # 5 % => onset/completion at 5 %/95 % of the drop
    analytical_sd_permil: float | None = Field(default=None, gt=0)  # lab precision, weights the fit
    min_weaning_drop_permil: float = Field(default=1.0, ge=0)  # smaller drops = "no clear signal"
    max_plausible_drop_permil: float = Field(default=5.0, gt=0)  # larger drops = more than one trophic step
    monte_carlo_draws: int = Field(default=1000, ge=0, le=20000)
    uncertainty: Literal["covariance", "bootstrap"] = "covariance"
    bootstrap_draws: int = Field(default=200, ge=0, le=5000)
    random_seed: int | None = 42
    qc: QCThresholds = QCThresholds()
    growth_overrides: dict[str, LinearGrowthOverride] = {}  # "species:tooth" -> simple linear age model
    growth_tables: list[GrowthTable] = []  # edited tables sent with this analysis
    time_averaging: bool = False  # treat each slice as an average over its age range
    increment_width_mm: float = Field(default=1.0, gt=0, le=20)
    growth_layer_offset_mm: float = Field(default=0.0, ge=0, le=50)
    inner_dentine_weight: float = Field(default=1.0, gt=0, le=1)  # 1 = all dentine in a slice counts equally
    seasonal_term: bool = False  # add a yearly up-and-down cycle to each curve
    season_period_months: float = Field(default=12.0, gt=0)
    adult_baselines: dict[str, AdultBaseline] = {}  # "site:species" or "species"
    constrain_adult_plateau: bool = False
    elbow_normalise: bool = True

    def override_for(self, species, tooth):
        for key, value in self.growth_overrides.items():
            if key.lower() == f"{species}:{tooth}".lower():
                return value
        return None

    def baseline_for(self, site, species):
        lower = {k.lower(): v for k, v in self.adult_baselines.items()}
        return lower.get(f"{site}:{species}".lower()) or lower.get(species.lower())


# Bone: many animals that died at different ages
class BoneSample(CollagenSample):
    """Bone collagen from one animal. Young animals need an age at death; adults only need age_class."""

    element: str | None = None  # e.g. rib, mandible
    age_class: Literal["adult", "non-adult"] | None = None  # blank = non-adult
    sex: Literal["f", "m"] | None = None
    age_months: float | None = Field(default=None, ge=0, le=600)  # best estimate of age at death
    age_min_months: float | None = Field(default=None, ge=0, le=600)  # range, e.g. from tooth wear or fusion
    age_max_months: float | None = Field(default=None, ge=0, le=600)

    @field_validator("age_class", mode="before")
    @classmethod
    def read_age_class(cls, value):
        if isinstance(value, str):
            word = value.strip().lower().replace("_", "-").replace(" ", "-")
            if word in {"adult", "a", "mature"}:
                return "adult"
            if word in {"non-adult", "nonadult", "juvenile", "subadult", "infant", "neonate", "young", "j"}:
                return "non-adult"
        return value

    @field_validator("sex", mode="before")
    @classmethod
    def read_sex(cls, value):
        if isinstance(value, str):
            word = value.strip().lower().rstrip("?")  # "F?" (probable female) counts as female
            return {"f": "f", "female": "f", "m": "m", "male": "m"}.get(word)  # anything else: unknown
        return value

    @model_validator(mode="after")
    def tidy(self):
        if self.age_months is not None:
            self.age_min_months = self.age_months if self.age_min_months is None else self.age_min_months
            self.age_max_months = self.age_months if self.age_max_months is None else self.age_max_months
        elif self.age_min_months is not None and self.age_max_months is not None:
            self.age_months = round((self.age_min_months + self.age_max_months) / 2, 4)
        if self.age_min_months is not None and self.age_max_months is not None:
            if self.age_min_months > self.age_max_months:
                raise ValueError("age_min_months is larger than age_max_months")
        if self.age_class != "adult" and self.age_months is None:
            raise ValueError("a non-adult needs age_months, or age_min_months and age_max_months")
        return self

    @property
    def is_adult(self):
        return self.age_class == "adult"


class TurnoverTable(BaseModel):
    """Share of bone collagen newly made per month, at each age (straight lines between the points)."""

    species: str
    label: str
    ages_months: list[float] = Field(min_length=2)
    renewed_per_month: list[float] = Field(min_length=2)
    source: str = ""
    placeholder: bool = False
    tbd_note: str | None = None

    @model_validator(mode="after")
    def check(self):
        if len(self.ages_months) != len(self.renewed_per_month):
            raise ValueError("ages_months and renewed_per_month must be the same length")
        if any(b <= a for a, b in zip(self.ages_months, self.ages_months[1:])):
            raise ValueError("turnover ages must increase")
        if not all(0 < r < 1 for r in self.renewed_per_month):
            raise ValueError("renewed_per_month must be between 0 and 1")
        return self


class BoneOptions(BaseModel):
    """Settings of the bone model. Priors are what is believed before seeing the data."""

    weaning_form: Literal["parabolic", "linear", "reverse"] = "parabolic"  # how milk gives way to food (WARN)
    # Left blank (None), these come from the species' entry in data/bone_priors.json.
    max_weaning_age_months: float | None = Field(default=None, gt=0, le=120)  # weaning ends no later than this
    enrichment_prior_mean: float | None = Field(default=None, ge=0, le=10)  # ‰ milk collagen above the mothers
    enrichment_prior_sd: float | None = Field(default=None, gt=0, le=5)
    newborn_offset_mean: float | None = Field(default=None, ge=-5, le=5)  # ‰ newborn bone above the mothers
    newborn_offset_sd: float | None = Field(default=None, gt=0, le=5)
    weaning_food_prior_sd: float = Field(default=3.0, gt=0, le=10)  # ‰ around the adult-female mean (WARN default)
    female_mean: float | None = Field(default=None, ge=-10, le=30)  # used when there are no adult females
    female_sd: float = Field(default=0.5, gt=0)
    qc: QCThresholds = QCThresholds()
    turnover_tables: list[TurnoverTable] = []  # edited tables sent with this analysis
    chains: int = Field(default=12, ge=4, le=24)  # run side by side, so more chains cost little
    warmup: int = Field(default=3000, ge=500, le=50000)
    keep: int = Field(default=4000, ge=500, le=50000)
    random_seed: int | None = 42


# Enamel: season of birth (δ18O) and rumen development (δ13C) along one molar
class EnamelSample(Sample):
    """One sample of tooth enamel carbonate. specimen_id is one tooth.

    erj_distance_mm is measured from the enamel-root junction (ERJ) up the crown, so larger
    values formed earlier in life.
    """

    tooth: str = Field(min_length=1)
    erj_distance_mm: float = Field(ge=0, le=150)
    d18O: float | None = Field(default=None, ge=-30, le=15)  # ‰ VPDB, enamel carbonate
    d13C: float | None = Field(default=None, ge=-30, le=15)  # ‰ VPDB, enamel carbonate
    sample_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def has_a_value(self):
        if self.d18O is None and self.d13C is None:
            raise ValueError("each enamel sample needs d18O, d13C or both")
        return self


class EnamelOptions(BaseModel):
    """Settings of the enamel analysis."""

    # Crown length formed in one year (mm): the cosine period is kept within this range.
    period_min_mm: float = Field(default=25.0, gt=0, le=200)
    period_max_mm: float = Field(default=80.0, gt=0, le=300)
    min_amplitude_permil: float = Field(default=0.5, ge=0)  # smaller δ18O cycles are not read as seasons
    min_rumen_rise_permil: float = Field(default=0.5, ge=0)  # smaller δ13C rises are not read as rumen development
    max_rumen_rise_permil: float = Field(default=3.0, gt=0)  # larger ones suggest a diet change as well
    # C3 or C4 diet: enamel δ13C minus this spacing is the diet's δ13C (large ruminants, Cerling & Harris 1999).
    enamel_diet_spacing_permil: float = Field(default=14.1, ge=0, le=20)
    enamel_diet_spacing_sd: float = Field(default=0.5, ge=0, le=5)
    # Plant end members for a pre-industrial atmosphere: modern means (C3 about -28.5, Kohn 2010; C4 about
    # -12.5) made about 1.5 per mil less negative for the Suess effect. Set modern values for modern animals.
    c3_plants_d13C: float = Field(default=-27.0, ge=-40, le=-15)
    c3_plants_sd: float = Field(default=2.0, gt=0, le=5)
    c4_plants_d13C: float = Field(default=-11.0, ge=-20, le=-5)
    c4_plants_sd: float = Field(default=1.0, gt=0, le=5)
    draws: int = Field(default=1000, ge=0, le=20000)
    random_seed: int | None = 42

    @model_validator(mode="after")
    def check_period(self):
        if self.period_min_mm >= self.period_max_mm:
            raise ValueError("period_min_mm must be smaller than period_max_mm")
        if self.c3_plants_d13C >= self.c4_plants_d13C:
            raise ValueError("c3_plants_d13C must be lower than c4_plants_d13C")
        return self
