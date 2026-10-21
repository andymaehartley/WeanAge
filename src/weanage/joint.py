"""One-stage hierarchical Bayesian model, fitted to the raw δ15N values of every specimen at once.

The two-stage model (inference.py) first fits each tooth, then compares the
summary ages. That throws away the shape of each tooth's uncertainty. Here the
weaning curves and the group comparison are estimated together:

    δ15N_ij ~ Normal(curve_i(age_ij + shift_i), σ_i)          each sample j of specimen i
    curve_i  = logistic with plateau post_i, drop_i, width s_i and milestone age m_i
    m_i      ~ Normal(μ_group, τ)                              animals vary around their group
    shift_i  ~ Normal(0, age-model SD)                         error in the tooth's growth table
    μ_group  ~ Normal(overall mean, 50),  τ ~ half-Cauchy(3)   (as in the two-stage model)
    s_i ~ log-normal(0, 1),  drop_i ~ Uniform(0, 20),  post_i flat,  σ_i ∝ 1/σ

m_i is the reported milestone itself (onset, midpoint or completion), so group
means and differences are directly about weaning ages.

It is fitted by Markov chain Monte Carlo: each curve parameter is nudged in turn and
the nudge kept with the usual Metropolis probability; σ, the age shift and μ are
drawn exactly from their conditional distributions.
All chains and specimens are updated together with numpy arrays, so it is fast
enough for the browser version too.
"""

import itertools
import math

import numpy as np

from .inference import middle95, split_rhat

# The curve itself is described in the tooth's own (recorded) ages, where the data pin
# it down well: c = the curve's middle, s = its width. The milestone in true age is
# m = c + k·s + shift. Writing it this way lets the sampler move freely.
PARAMS = ["c", "log_s", "post", "drop"]  # updated by Metropolis steps


def milestone_offset(milestone, q):
    """How far the milestone lies from the curve's middle, in units of the width s."""
    half = math.log((1 - q) / q)
    return {"onset": -half, "midpoint": 0.0, "completion": half}[milestone]


def specimens_from_results(results, group_by, milestone="midpoint", q=0.05, min_points=6):
    """Pick the data the model needs from the analysis results (QC-passed samples only).

    A specimen is left out (and named in `skipped`) if it has too few samples, or if its
    own logistic fit puts the milestone outside the ages its tooth covers: the joint
    model should not be driven by extrapolations.
    """
    chosen, skipped = [], []
    k = milestone_offset(milestone, q)
    for r in results:
        points = [p for p in r["points"] if p.get("used_in_fit")]
        fit = next((f["params"] for f in r.get("fits", []) if f["model"] == "logistic" and f["converged"]), None)
        ages = [p["age_months"] for p in points]
        if len(points) < min_points:
            skipped.append(f"{r['specimen_id']}: fewer than {min_points} usable samples")
            continue
        if fit and not min(ages) <= fit["t_mid"] + k * fit["scale"] <= max(ages):
            skipped.append(f"{r['specimen_id']}: the logistic {milestone} lies outside the sampled ages")
            continue
        chosen.append({
            "specimen_id": r["specimen_id"],
            "group": " · ".join(str(r.get(g) or "—") for g in group_by),
            "ages": np.array([p["age_months"] for p in points], dtype=float),
            "d15N": np.array([p["d15N"] for p in points], dtype=float),
            "age_sd": float(r.get("age_sd_months") or 0.0),
            "logistic": fit,
        })
    return chosen, skipped


def starting_values(spec):
    """Where each chain starts: the specimen's own logistic fit if there is one,
    otherwise a rough curve from its early and late levels and where δ15N crosses halfway."""
    fit = spec.get("logistic")
    if fit and fit["drop"] > 0:  # keep the start inside the prior's range (0-20‰), or the chain could never move
        return {"post": fit["post"], "drop": min(fit["drop"], 15.0), "middle": fit["t_mid"], "s": max(fit["scale"], 0.05)}
    t, y = spec["ages"], spec["d15N"]
    order = np.argsort(t)
    t, y = t[order], y[order]
    quarter = max(len(y) // 4, 2)
    pre, post = y[:quarter].mean(), y[-quarter:].mean()
    drop = max(pre - post, 0.3)
    below = np.nonzero(y < post + drop / 2)[0]
    middle = t[below[0]] if len(below) else float(np.median(t))
    return {"post": post, "drop": drop, "middle": middle, "s": max(np.ptp(t) / 20, 0.2)}


def log_density_tau(tau, spread, n, tau_scale):
    """τ's posterior (up to a constant): normal spread of n animals, half-Cauchy prior,
    plus log τ because the random-walk step is taken on log τ."""
    return -n * np.log(tau) - 0.5 * spread / tau ** 2 - np.log1p((tau / tau_scale) ** 2) + np.log(tau)


def joint_bayes(specimens, milestone="midpoint", q=0.05, chains=4, warmup=2000, keep=3000,
                tau_scale=3.0, prior_sd=50.0, seed=0):
    rng = np.random.default_rng(seed)
    n = len(specimens)
    names, group_of = np.unique([s["group"] for s in specimens], return_inverse=True)
    k = milestone_offset(milestone, q)

    # Pad every specimen's samples to the same length; `mask` marks real samples.
    longest = max(len(s["ages"]) for s in specimens)
    T = np.zeros((n, longest))
    Y = np.zeros((n, longest))
    mask = np.zeros((n, longest))
    for i, s in enumerate(specimens):
        T[i, :len(s["ages"])], Y[i, :len(s["ages"])], mask[i, :len(s["ages"])] = s["ages"], s["d15N"], 1
    count = mask.sum(axis=1)
    age_sd = np.array([s["age_sd"] for s in specimens])

    # Starting values for every chain (with a little jitter so the chains differ).
    start = [starting_values(s) for s in specimens]
    shape = (chains, n)
    s0 = np.array([v["s"] for v in start])
    p = {
        "log_s": np.log(s0) + rng.normal(0, 0.1, shape),
        "post": np.array([v["post"] for v in start]) + rng.normal(0, 0.05, shape),
        "drop": np.array([v["drop"] for v in start]) * np.exp(rng.normal(0, 0.05, shape)),
        "c": np.array([v["middle"] for v in start]) + rng.normal(0, 0.2, shape),
    }
    shift = np.zeros(shape)

    def milestone_age(q_):
        return q_["c"] + k * np.exp(q_["log_s"]) + shift

    sigma2 = np.full(shape, 0.1)
    m0 = milestone_age(p)
    mu = np.array([[m0[c, group_of == g].mean() for g in range(len(names))] for c in range(chains)])
    tau = np.full(chains, 1.0)
    step = {"c": 0.3, "log_s": 0.2, "post": 0.1, "drop": 0.1}
    step = {key: np.full(shape, value) for key, value in step.items()}

    def squared_error(q_):
        """Sum over samples of (data - curve)², one value per chain and specimen."""
        width = np.exp(q_["log_s"])[..., None]
        z = np.clip((T - q_["c"][..., None]) / width, -60, 60)
        curve = q_["post"][..., None] + q_["drop"][..., None] / (1 + np.exp(z))
        return (((Y - curve) ** 2) * mask).sum(axis=-1)

    def log_prior(q_):
        lp = -0.5 * ((milestone_age(q_) - mu[:, group_of]) / tau[:, None]) ** 2
        lp += -0.5 * q_["log_s"] ** 2
        return lp + np.where((q_["drop"] > 0) & (q_["drop"] < 20), 0.0, -np.inf)

    def log_post(q_):
        return -0.5 * squared_error(q_) / sigma2 + log_prior(q_)

    total = warmup + keep
    m_draws = np.empty((chains, keep, n))
    mu_draws = np.empty((chains, keep, len(names)))
    tau_draws = np.empty((chains, keep))
    accepted = {key: np.zeros(shape) for key in PARAMS}
    current = log_post(p)
    for it in range(total):
        # 1. Metropolis: nudge each curve parameter for every chain and specimen at once.
        for key in PARAMS:
            trial = dict(p)
            trial[key] = p[key] + step[key] * rng.normal(size=shape)
            proposed = log_post(trial)
            keep_it = np.log(rng.random(shape)) < proposed - current
            p[key] = np.where(keep_it, trial[key], p[key])
            current = np.where(keep_it, proposed, current)
            accepted[key] += keep_it
        # 2. Measurement scatter σ² drawn exactly (inverse-gamma).
        sigma2 = np.maximum(0.5 * squared_error(p) / rng.gamma(count / 2, size=shape), 1e-6)
        # 3. Age-model shift drawn exactly (normal): its own prior combined with the group's pull.
        recorded = p["c"] + k * np.exp(p["log_s"])  # milestone in the tooth's recorded ages
        precision = np.where(age_sd > 0, 1 / np.where(age_sd > 0, age_sd, 1) ** 2, np.inf) + 1 / tau[:, None] ** 2
        mean = ((mu[:, group_of] - recorded) / tau[:, None] ** 2) / precision
        shift = np.where(age_sd > 0, rng.normal(mean, 1 / np.sqrt(precision)), 0.0)
        m = recorded + shift
        # 4. Group means drawn exactly (normal). Each chain uses only its own values, so the
        #    chains stay independent (which the R̂ check assumes).
        centre = m.mean(axis=1)
        for g in range(len(names)):
            members = m[:, group_of == g]
            precision_g = members.shape[1] / tau ** 2 + 1 / prior_sd ** 2
            mean_g = (members.sum(axis=1) / tau ** 2 + centre / prior_sd ** 2) / precision_g
            mu[:, g] = rng.normal(mean_g, 1 / np.sqrt(precision_g))
        # 5. τ (spread between animals) by a Metropolis step on its logarithm.
        spread = ((m - mu[:, group_of]) ** 2).sum(axis=1)

        proposal = tau * np.exp(rng.normal(0, 0.4, chains))
        gain = log_density_tau(proposal, spread, n, tau_scale) - log_density_tau(tau, spread, n, tau_scale)
        tau = np.where(np.log(rng.random(chains)) < gain, proposal, tau)
        current = log_post(p)
        # During warm-up, tune each step size towards ~35 % accepted nudges.
        if it < warmup and (it + 1) % 50 == 0:
            for key in PARAMS:
                step[key] *= np.exp(accepted[key] / 50 - 0.35)
                accepted[key][:] = 0
        if it >= warmup:
            j = it - warmup
            m_draws[:, j], mu_draws[:, j], tau_draws[:, j] = m, mu, tau
    return names, group_of, m_draws, mu_draws, tau_draws


def joint_summary(results, group_by, milestone="midpoint", q=0.05, seed=0):
    """Same layout as the two-stage summary (inference.bayes_summary), so the app shows it the same way.
    Returns (summary or None if fewer than 3 specimens can be used, list of specimens left out and why)."""
    specimens, skipped = specimens_from_results(results, group_by, milestone, q)
    if len(specimens) < 3:
        return None, skipped
    names, group_of, m, mu, tau = joint_bayes(specimens, milestone, q, seed=seed)
    m_flat, mu_flat = m.reshape(-1, len(specimens)), mu.reshape(-1, len(names))
    groups = []
    for g, name in enumerate(names):
        low, high = middle95(mu_flat[:, g])
        groups.append({"group": str(name), "n": int((group_of == g).sum()), "mean": float(mu_flat[:, g].mean()),
                       "ci_low": low, "ci_high": high})
    pairs = []
    for a, b in itertools.combinations(range(len(names)), 2):
        diff = mu_flat[:, a] - mu_flat[:, b]
        low, high = middle95(diff)
        pairs.append({"group_a": str(names[a]), "group_b": str(names[b]), "prob_a_earlier": float(np.mean(diff < 0)),
                      "difference_mean": float(diff.mean()), "difference_ci_low": low, "difference_ci_high": high})
    rows = []
    for i, s in enumerate(specimens):
        low, high = middle95(m_flat[:, i])
        own = s["logistic"]["t_mid"] + milestone_offset(milestone, q) * s["logistic"]["scale"] if s["logistic"] else None
        rows.append({"specimen_id": s["specimen_id"], "group": s["group"], "observed": own,
                     "shrunk": float(m_flat[:, i].mean()), "ci_low": low, "ci_high": high})
    tau_low, tau_high = middle95(tau.ravel())
    rhat = max([split_rhat(tau)] + [split_rhat(mu[:, :, g]) for g in range(len(names))]
               + [split_rhat(m[:, :, i]) for i in range(len(specimens))])
    return {"method": "one-stage", "groups": groups, "pairs": pairs, "specimens": rows,
            "tau_mean": float(tau.mean()), "tau_ci_low": tau_low, "tau_ci_high": tau_high,
            "rhat_max": rhat, "draws": int(tau.size)}, skipped
