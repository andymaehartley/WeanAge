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

    d34S: float | None = Field(default=None, ge=-40, le=40)  # ‰ VCDT; shifts suggest a move or diet change
    labels: dict[str, str] = {}  # other columns of the table (e.g. sex, burial type), for grouping in Compare
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
    d13C_mean: float | None = Field(default=None, ge=-35, le=-5)  # optional, for the milk share
    d13C_sd: float = Field(default=0.5, gt=0)


class WeaningFood(BaseModel):
    """A weaning food other than the adult diet, as the collagen it would give on its own (‰)."""

    name: str = Field(min_length=1)
    d15N: float
    d15N_sd: float = Field(default=0.5, gt=0)
    d13C: float | None = None
    d13C_sd: float = Field(default=0.5, gt=0)


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
    # Stress episodes: δ15N this far above the weaning curve while δ13C is this far below its expected level.
    stress_d15N_permil: float = Field(default=0.5, gt=0)
    stress_d13C_permil: float = Field(default=0.3, gt=0)
    d34S_min_shift_permil: float = Field(default=2.0, gt=0)  # smaller δ34S shifts are not reported
    adult_baselines: dict[str, AdultBaseline] = {}  # "site:species" or "species"
    # Breast-milk share per increment (needs an adult-female baseline). Blank enrichment = the species prior.
    nursing_enrichment_d15N: float | None = Field(default=None, ge=0, le=6)
    nursing_enrichment_d15N_sd: float | None = Field(default=None, gt=0, le=3)
    nursing_enrichment_d13C: float = Field(default=1.0, ge=-1, le=3)  # Fuller et al. 2006
    nursing_enrichment_d13C_sd: float = Field(default=0.5, gt=0, le=2)
    weaning_food: WeaningFood | None = None
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
    sr87_86: float | None = Field(default=None, ge=0.69, le=0.75)  # 87Sr/86Sr of the enamel
    sample_index: int | None = Field(default=None, ge=0)
    # Weaning age of the same animal (e.g. from its dentine δ15N), for the season of weaning.
    weaning_age_months: float | None = Field(default=None, ge=0, le=120)
    weaning_age_sd_months: float | None = Field(default=None, ge=0, le=60)

    @model_validator(mode="after")
    def has_a_value(self):
        if self.d18O is None and self.d13C is None and self.sr87_86 is None:
            raise ValueError("each enamel sample needs d18O, d13C or sr87_86")
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
    # Calendar: the month (1 = January, 7.5 = mid-July) in which enamel δ18O peaks. It places the rumen
    # transition and strontium shifts in the year. Summer in the northern hemisphere; check locally.
    d18O_max_month: float = Field(default=7.0, ge=1, lt=13)
    # Birth month: a reference tooth of the same type with a known birth month and its birth index.
    # Needed to turn birth indices (and weaning ages) into calendar months; there is no default.
    reference_birth_index: float | None = Field(default=None, ge=0, lt=1)
    reference_birth_month: float | None = Field(default=None, ge=1, lt=13)
    # Mobility: 87Sr/86Sr shifts smaller than this are not reported; optional range of local values.
    sr_min_shift: float = Field(default=0.0005, gt=0, le=0.05)
    local_sr_min: float | None = Field(default=None, ge=0.69, le=0.75)
    local_sr_max: float | None = Field(default=None, ge=0.69, le=0.75)
    # Undo mineralisation smoothing: crown length over which each sample's enamel matured (0 = off).
    mineralisation_length_mm: float = Field(default=0.0, ge=0, le=60)
    draws: int = Field(default=1000, ge=0, le=20000)
    random_seed: int | None = 42

    @model_validator(mode="after")
    def check_period(self):
        if self.period_min_mm >= self.period_max_mm:
            raise ValueError("period_min_mm must be smaller than period_max_mm")
        if self.c3_plants_d13C >= self.c4_plants_d13C:
            raise ValueError("c3_plants_d13C must be lower than c4_plants_d13C")
        if (self.reference_birth_index is None) != (self.reference_birth_month is None):
            raise ValueError("give both reference_birth_index and reference_birth_month, or neither")
        if self.local_sr_min is not None and self.local_sr_max is not None and self.local_sr_min >= self.local_sr_max:
            raise ValueError("local_sr_min must be smaller than local_sr_max")
        return self


# Payne (1973) mandible wear stages for sheep and goats, as age ranges in months.
PAYNE_STAGES = {"A": (0, 2), "B": (2, 6), "C": (6, 12), "D": (12, 24), "E": (24, 36), "F": (36, 48),
                "G": (48, 72), "H": (72, 96), "I": (96, 120)}
PAYNE_BOUNDS = [0.0, 2, 6, 12, 24, 36, 48, 72, 96, 120]


class KilloffSample(Sample):
    """One aged mandible (or loose tooth). Give a Payne wear stage, or an age range in months.

    A stage may span several, written "D/E" or "D-E": the mandible could be either.
    """

    payne_stage: str | None = None
    age_min_months: float | None = Field(default=None, ge=0, le=600)
    age_max_months: float | None = Field(default=None, gt=0, le=600)

    @model_validator(mode="after")
    def has_an_age(self):
        if self.payne_stage:
            letters = [c for c in self.payne_stage.upper() if c.isalpha()]
            if not letters or len(letters) > 2 or any(c not in PAYNE_STAGES for c in letters):
                raise ValueError(f"payne_stage {self.payne_stage!r} is not a Payne stage A–I, or a range such as D/E")
            first, last = sorted(letters)[0], sorted(letters)[-1]
            if self.age_min_months is None:
                self.age_min_months = float(PAYNE_STAGES[first][0])
            if self.age_max_months is None:
                self.age_max_months = float(PAYNE_STAGES[last][1])
        if self.age_min_months is None or self.age_max_months is None:
            raise ValueError("each mandible needs payne_stage, or age_min_months and age_max_months")
        if self.age_min_months >= self.age_max_months:
            raise ValueError("age_min_months must be smaller than age_max_months")
        return self


class KilloffOptions(BaseModel):
    """Settings of the kill-off profiles."""

    class_bounds_months: list[float] = Field(default=PAYNE_BOUNDS, min_length=3, max_length=20)
    bootstrap_draws: int = Field(default=1000, ge=0, le=10000)
    permutations: int = Field(default=1000, ge=0, le=10000)
    random_seed: int | None = 42

    @field_validator("class_bounds_months")
    @classmethod
    def rising(cls, bounds):
        if any(b >= c for b, c in zip(bounds, bounds[1:])) or bounds[0] < 0:
            raise ValueError("class_bounds_months must start at 0 or more and rise")
        return bounds


class MixingSample(Sample):
    """One bone or dentine collagen sample, for estimating the diet's make-up."""

    d13C: float = Field(ge=-35, le=-5)
    d15N: float = Field(ge=-5, le=30)
    d34S: float | None = Field(default=None, ge=-40, le=40)


class DietSource(BaseModel):
    """A food group's isotope values (of its protein, as eaten), mean and SD in ‰."""

    name: str = Field(min_length=1)
    d13C: float
    d13C_sd: float = Field(gt=0)
    d15N: float
    d15N_sd: float = Field(gt=0)
    d34S: float | None = None
    d34S_sd: float | None = Field(default=None, gt=0)


class MixingOptions(BaseModel):
    """Settings of the collagen diet mixing model. Sources and offsets default to data/diet_sources.json."""

    sources: list[DietSource] | None = Field(default=None, min_length=2, max_length=6)
    # Collagen minus diet (‰), mean and SD.
    offset_d13C: float | None = None
    offset_d13C_sd: float | None = Field(default=None, ge=0)
    offset_d15N: float | None = None
    offset_d15N_sd: float | None = Field(default=None, ge=0)
    offset_d34S: float | None = None
    offset_d34S_sd: float | None = Field(default=None, ge=0)
    measurement_sd_permil: float = Field(default=0.2, ge=0, le=2)
    draws: int = Field(default=20000, ge=1000, le=200000)
    random_seed: int | None = 42


# Dental development (humans): Moorrees et al. (1963) stages of each tooth
MOORREES_STAGES = ["Ci", "Cco", "Coc", "Cr1/2", "Cr3/4", "Crc", "Ri", "R1/4", "R1/2", "R3/4", "Rc", "A1/2", "Ac"]
TEETH = ["di1", "di2", "dc", "dm1", "dm2", "I1", "I2", "C", "PM1", "PM2", "M1", "M2", "M3"]
TOOTH_ALIASES = {"p1": "PM1", "p3": "PM1", "pm3": "PM1", "p2": "PM2", "p4": "PM2", "pm4": "PM2", "dm3": "dm1", "dm4": "dm2",
                 "dp3": "dm1", "dp4": "dm2", "di1": "di1", "di2": "di2", "dc": "dc", "dm1": "dm1", "dm2": "dm2"}


def tooth_name(text):
    """'lower left M1', 'M1', 'dm2' or 'P4' -> a name in TEETH (side and jaw are ignored)."""
    t = str(text).lower()
    for word in ("upper", "lower", "left", "right", "maxillary", "mandibular"):
        t = t.replace(word, "")
    t = "".join(c for c in t if c.isalnum())
    if t in TOOTH_ALIASES:
        return TOOTH_ALIASES[t]
    match = next((name for name in TEETH if name.lower() == t), None)
    if match is None:
        raise ValueError(f"tooth {text!r} is not one of {', '.join(TEETH)} (P3/P4 are read as PM1/PM2)")
    return match


def stage_name(text):
    """'Cr ½', 'cr1/2', 'Cli' or a number 1-13 -> a Moorrees stage."""
    t = str(text).strip().lower().replace("½", "1/2").replace("¾", "3/4").replace("¼", "1/4")
    t = "".join(c for c in t if c.isalnum() or c == "/")
    if t.isdigit() and 1 <= int(t) <= len(MOORREES_STAGES):
        return MOORREES_STAGES[int(t) - 1]
    if t == "cli":  # cleft initiation in molars falls between Crc and R1/4
        return "Ri"
    match = next((s for s in MOORREES_STAGES if s.lower() == t), None)
    if match is None:
        raise ValueError(f"stage {text!r} is not a Moorrees stage ({', '.join(MOORREES_STAGES)}, or 1-13)")
    return match


class DentalSample(Sample):
    """One tooth of one individual (specimen_id) and its formation stage."""

    tooth: str
    stage: str

    @field_validator("tooth", mode="after")
    @classmethod
    def known_tooth(cls, value):
        return tooth_name(value)

    @field_validator("stage", mode="before")
    @classmethod
    def known_stage(cls, value):
        return stage_name(value) if value is not None else value


class DentalOptions(BaseModel):
    """Settings of the dental age estimate. Formation ages come from data/dental_stages.json."""

    interval_z: float = Field(default=1.96, gt=0, le=4)  # age range given to the bone calculation: estimate ± z·SD
    discordance_z: float = Field(default=2.0, gt=0, le=5)  # teeth further than this many SDs from the estimate are flagged
    random_seed: int | None = 42


class LehSample(Sample):
    """One linear enamel hypoplasia defect. specimen_id is the individual (as in the tooth calculation).

    defect_mm is measured from the cemento-enamel junction (CEJ) up to the defect; crown_height_mm is
    the unworn crown height on the same face. Blank crown height: the tooth's height is unknown and the
    defect cannot be dated.
    """

    tooth: str
    defect_mm: float = Field(ge=0, le=30)
    crown_height_mm: float = Field(gt=0, le=30)
    defect_id: str | None = None

    @field_validator("tooth", mode="after")
    @classmethod
    def known_tooth(cls, value):
        return tooth_name(value)

    @model_validator(mode="after")
    def on_the_crown(self):
        if self.defect_mm > self.crown_height_mm:
            raise ValueError("defect_mm is larger than crown_height_mm: the defect would be above the cusp")
        return self


class DentineContext(BaseModel):
    """What the tooth calculation found for one individual, to set defects against."""

    onset: float | None = None
    completion: float | None = None
    midpoint: float | None = None
    stress: list[tuple[float, float]] = []


class LehOptions(BaseModel):
    measurement_sd_mm: float = Field(default=0.2, ge=0, le=3)
    draws: int = Field(default=2000, ge=100, le=20000)
    dentine: dict[str, DentineContext] = {}  # specimen_id -> tooth-calculation results
    random_seed: int | None = 42


class LifeSample(Sample):
    """One skeleton with an age-at-death range. Blank age_max = open-ended (an adult of at least age_min)."""

    age_min_years: float | None = Field(default=None, ge=0, le=110)
    age_max_years: float | None = Field(default=None, gt=0, le=120)
    age_min_months: float | None = Field(default=None, ge=0, le=1320)
    age_max_months: float | None = Field(default=None, gt=0, le=1440)
    sex: str | None = None

    @model_validator(mode="after")
    def in_years(self):
        if self.age_min_years is None and self.age_min_months is not None:
            self.age_min_years = self.age_min_months / 12
        if self.age_max_years is None and self.age_max_months is not None:
            self.age_max_years = self.age_max_months / 12
        if self.age_min_years is None:
            raise ValueError("each skeleton needs age_min_years (or age_min_months)")
        if self.age_max_years is not None and self.age_max_years <= self.age_min_years:
            raise ValueError("the age range ends before it starts")
        return self


class LifeTableOptions(BaseModel):
    # Single years up to 5 show deaths around weaning; an open-ended adult age (e.g. 50+) is spread up to the last boundary.
    class_bounds_years: list[float] = Field(default=[0, 1, 2, 3, 4, 5, 10, 15, 20, 30, 40, 50, 60, 80], min_length=3, max_length=30)
    bootstrap_draws: int = Field(default=1000, ge=0, le=10000)
    permutations: int = Field(default=1000, ge=0, le=10000)
    siler: bool = True  # also fit a Siler hazard model to the age ranges
    random_seed: int | None = 42

    @field_validator("class_bounds_years")
    @classmethod
    def rising(cls, bounds):
        if any(b >= c for b, c in zip(bounds, bounds[1:])) or bounds[0] != 0:
            raise ValueError("class_bounds_years must start at 0 and rise")
        return bounds


class MobilitySample(Sample):
    """One bulk enamel sample (or a local baseline: role = baseline, e.g. fauna or plants for strontium).

    d18O is enamel carbonate (‰ VPDB) or phosphate (‰ VSMOW), as d18O_material says.
    """

    tooth: str | None = None
    d18O: float | None = Field(default=None, ge=-30, le=30)
    d18O_material: Literal["carbonate", "phosphate"] = "carbonate"
    sr87_86: float | None = Field(default=None, ge=0.69, le=0.75)
    role: Literal["sample", "baseline"] = "sample"

    @field_validator("d18O_material", "role", mode="before")
    @classmethod
    def lower(cls, value, info):
        if value is None:  # a blank cell
            return {"d18O_material": "carbonate", "role": "sample"}[info.field_name]
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def has_a_value(self):
        if self.d18O is None and self.sr87_86 is None:
            raise ValueError("each sample needs d18O, sr87_86 or both")
        return self


class MobilityOptions(BaseModel):
    # SD of a drinking-water value predicted from enamel (regression error); Pollard et al. 2011 argue it can be larger.
    drinking_water_sd: float = Field(default=1.0, ge=0, le=5)
    local_d18O_dw_min: float | None = Field(default=None, ge=-30, le=10)  # local drinking water, ‰ VSMOW
    local_d18O_dw_max: float | None = Field(default=None, ge=-30, le=10)
    local_sr_min: float | None = Field(default=None, ge=0.69, le=0.75)  # overrides the baseline samples
    local_sr_max: float | None = Field(default=None, ge=0.69, le=0.75)
    baseline_sd_multiplier: float = Field(default=2.0, gt=0, le=4)  # local Sr = baseline mean ± this × SD
    random_seed: int | None = 42
