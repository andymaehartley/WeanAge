"""Are weaning ages really different between groups (sites, species, periods)?

Each specimen's estimate comes with its own uncertainty, which these methods use:

* random-effects group means - a group average that allows animals to genuinely
  differ (τ), plus a test of "any difference at all" and Holm-corrected pair tests;
* a permutation test - shuffle the group labels and see how often chance alone
  gives differences this large;
* a hierarchical Bayesian model - each animal's estimate is pulled towards its
  group's average, and we get direct probabilities such as P(pigs weaned earlier).
"""

import itertools
import math

import numpy as np
import pandas as pd
from scipy import stats

Z95 = 1.959964  # 95 % of a normal distribution lies within ±1.96 SD


def select_estimates(rows, milestone, model, group_by):
    """One row per specimen with its estimate, standard error (se) and group name."""
    df = pd.DataFrame(list(rows))
    if df.empty:
        return df
    df = df[df["is_best"]] if model is None else df[df["model"] == model]
    df = df[df[milestone].notna()].copy()
    df["group"] = df[group_by].fillna("—").astype(str).agg(" · ".join, axis=1)
    # Standard error from the 95 % interval (only completion ages have intervals).
    df["se"] = np.nan
    if milestone == "completion":
        df["se"] = (df["completion_ci_high"] - df["completion_ci_low"]) / (2 * Z95)
    df.loc[~(df["se"] > 0), "se"] = np.nan
    if df["se"].isna().any():
        fallback = df["se"].median() if df["se"].notna().any() else max(df[milestone].std(ddof=1) / 4, 0.1)
        df["se"] = df["se"].fillna(fallback if np.isfinite(fallback) else 0.5)
    return df


def random_effects(y, se):
    """DerSimonian-Laird: the group mean, its standard error, and τ (real animal-to-animal SD)."""
    if len(y) < 2:
        return float(y[0]), float(se[0]), 0.0
    w = 1 / se ** 2
    simple_mean = np.sum(w * y) / np.sum(w)
    q = np.sum(w * (y - simple_mean) ** 2)
    c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max((q - (len(y) - 1)) / c, 0.0) if c > 0 else 0.0
    w = 1 / (se ** 2 + tau2)
    return float(np.sum(w * y) / np.sum(w)), float(math.sqrt(1 / np.sum(w))), float(math.sqrt(tau2))


def holm(p_values):
    """Holm correction: makes p-values stricter when many pairs are tested."""
    adjusted, running = [0.0] * len(p_values), 0.0
    for rank, i in enumerate(np.argsort(p_values)):
        running = max(running, min(1.0, (len(p_values) - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted


def permutation_test(y, labels, n_perm=5000, seed=0):
    groups = np.unique(labels)
    if len(groups) < 2 or len(y) <= len(groups):
        return None

    def spread_between_groups(lab):
        return sum((lab == g).sum() * (y[lab == g].mean() - y.mean()) ** 2 for g in groups)

    observed = spread_between_groups(labels)
    rng = np.random.default_rng(seed)
    hits = sum(spread_between_groups(rng.permutation(labels)) >= observed - 1e-12 for _ in range(n_perm))
    return (hits + 1) / (n_perm + 1)


def hierarchical_bayes(y, se, groups, chains=4, iterations=3000, burn=1000, tau_scale=3.0, prior_sd=50.0, seed=0):
    """Gibbs sampler for the model
        estimate_i ~ Normal(true_i, se_i)      true_i ~ Normal(group mean, τ)
        group mean ~ Normal(overall mean, 50)  τ ~ half-Cauchy(3)
    Each step draws one unknown given the others; τ uses a Metropolis step.
    """
    names, group_of = np.unique(groups, return_inverse=True)
    rng = np.random.default_rng(seed)
    keep = iterations - burn
    mu_draws = np.empty((chains, keep, len(names)))
    true_draws = np.empty((chains, keep, len(y)))
    tau_draws = np.empty((chains, keep))

    def log_density_tau(tau, true, mu):
        if tau <= 0:
            return -np.inf
        spread = np.sum((true - mu[group_of]) ** 2)
        return -len(y) * math.log(tau) - 0.5 * spread / tau ** 2 - math.log1p((tau / tau_scale) ** 2) + math.log(tau)

    for c in range(chains):
        tau = abs(rng.normal(1.0, 0.5)) + 0.1
        mu = np.array([y[group_of == g].mean() for g in range(len(names))]) + rng.normal(0, 0.5, len(names))
        for it in range(iterations):
            precision = 1 / se ** 2 + 1 / tau ** 2
            true = rng.normal((y / se ** 2 + mu[group_of] / tau ** 2) / precision, 1 / np.sqrt(precision))
            for g in range(len(names)):
                members = true[group_of == g]
                precision_g = len(members) / tau ** 2 + 1 / prior_sd ** 2
                mean_g = (members.sum() / tau ** 2 + y.mean() / prior_sd ** 2) / precision_g
                mu[g] = rng.normal(mean_g, 1 / math.sqrt(precision_g))
            proposal = tau * math.exp(rng.normal(0, 0.5))
            if math.log(rng.random()) < log_density_tau(proposal, true, mu) - log_density_tau(tau, true, mu):
                tau = proposal
            if it >= burn:
                mu_draws[c, it - burn], true_draws[c, it - burn], tau_draws[c, it - burn] = mu, true, tau
    return names, mu_draws, true_draws, tau_draws


def split_rhat(draws):
    """R̂: compares the chains with each other; close to 1 means they agree (have converged)."""
    half = draws.shape[1] // 2
    chains = np.concatenate([draws[:, :half], draws[:, half:2 * half]])
    n = chains.shape[1]
    within = chains.var(axis=1, ddof=1).mean()
    between = n * chains.mean(axis=1).var(ddof=1)
    return 1.0 if within <= 0 else float(math.sqrt(((n - 1) / n * within + between / n) / within))


def middle95(values):
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def bayes_summary(df, milestone, seed):
    names, mu, true, tau = hierarchical_bayes(df[milestone].to_numpy(float), df["se"].to_numpy(float),
                                              df["group"].to_numpy(), seed=seed)
    mu_flat, true_flat = mu.reshape(-1, len(names)), true.reshape(-1, len(df))
    groups = []
    for g, name in enumerate(names):
        low, high = middle95(mu_flat[:, g])
        groups.append({"group": str(name), "n": int((df["group"] == name).sum()), "mean": float(mu_flat[:, g].mean()),
                       "ci_low": low, "ci_high": high})
    pairs = []
    for a, b in itertools.combinations(range(len(names)), 2):
        diff = mu_flat[:, a] - mu_flat[:, b]
        low, high = middle95(diff)
        pairs.append({"group_a": str(names[a]), "group_b": str(names[b]), "prob_a_earlier": float(np.mean(diff < 0)),
                      "difference_mean": float(diff.mean()), "difference_ci_low": low, "difference_ci_high": high})
    specimens = []
    for i, row in enumerate(df.itertuples()):
        low, high = middle95(true_flat[:, i])
        specimens.append({"specimen_id": row.specimen_id, "group": row.group, "observed": float(getattr(row, milestone)),
                          "shrunk": float(true_flat[:, i].mean()), "ci_low": low, "ci_high": high})
    tau_low, tau_high = middle95(tau.ravel())
    rhat = max([split_rhat(tau)] + [split_rhat(mu[:, :, g]) for g in range(len(names))])
    return {"groups": groups, "pairs": pairs, "specimens": specimens, "tau_mean": float(tau.mean()),
            "tau_ci_low": tau_low, "tau_ci_high": tau_high, "rhat_max": rhat, "draws": int(tau.size)}


def compare_groups(rows, group_by, milestone="completion", model=None, bayes=True, seed=0, results=None,
                   threshold=0.05):
    """bayes: True or "two_stage" (pool the specimen estimates), "one_stage" (fit the raw
    δ15N values of every specimen together; needs the analysis `results`), or False."""
    out = {"milestone": milestone, "model": model or "best (AICc)", "group_by": list(group_by), "groups": [],
           "q_between": None, "q_df": 0, "q_p": None, "pairwise": [], "permutation_p": None, "bayes": None, "notes": []}
    df = select_estimates(rows, milestone, model, list(group_by))
    if df.empty:
        out["notes"].append("No estimates to compare")
        return out
    if milestone != "completion":
        out["notes"].append("Specimen uncertainties are only available for completion; a common SE was assumed")

    for name, sub in df.groupby("group"):
        mean, se, tau = random_effects(sub[milestone].to_numpy(float), sub["se"].to_numpy(float))
        out["groups"].append({"group": str(name), "n": len(sub), "mean": mean, "se": se,
                              "ci_low": mean - Z95 * se, "ci_high": mean + Z95 * se, "tau": tau})

    groups = out["groups"]
    if len(groups) >= 2:
        means = np.array([g["mean"] for g in groups])
        w = 1 / np.array([g["se"] for g in groups]) ** 2
        q = float(np.sum(w * (means - np.sum(w * means) / np.sum(w)) ** 2))
        out.update(q_between=q, q_df=len(groups) - 1, q_p=float(stats.chi2.sf(q, len(groups) - 1)))
        for a, b in itertools.combinations(groups, 2):
            diff, se = a["mean"] - b["mean"], math.hypot(a["se"], b["se"])
            z = diff / se if se > 0 else 0.0
            out["pairwise"].append({"group_a": a["group"], "group_b": b["group"], "difference": diff, "se": se,
                                    "z": z, "p": float(2 * stats.norm.sf(abs(z)))})
        for pair, adjusted in zip(out["pairwise"], holm([p["p"] for p in out["pairwise"]])):
            pair["p_holm"] = adjusted
        out["permutation_p"] = permutation_test(df[milestone].to_numpy(float), df["group"].to_numpy(), seed=seed)
        if any(g["n"] < 3 for g in groups):
            out["notes"].append("Some groups have fewer than 3 specimens; their means are poorly constrained")

    if bayes == "one_stage":
        from .joint import joint_summary  # imported here: joint.py itself uses this module

        out["bayes"], skipped = joint_summary(results or [], list(group_by), milestone, threshold, seed)
        out["notes"] += [f"Left out of the one-stage model: {s}" for s in skipped]
        if any(p.get("age_min") is not None for r in results or [] for p in r["points"]):
            out["notes"].append("The one-stage model fits each sample at its centre age (time averaging is not applied)")
    elif bayes and len(df) >= 3:
        out["bayes"] = bayes_summary(df, milestone, seed)
    if out["bayes"] and out["bayes"]["rhat_max"] > 1.05:
        out["notes"].append(f"Bayesian chains have not fully converged (R̂ = {out['bayes']['rhat_max']:.2f})")
    return out
