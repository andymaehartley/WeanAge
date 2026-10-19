"""Formal comparison of weaning ages between groups (sites, species, periods).

Each specimen contributes an estimate with its own uncertainty, so groups are
compared with methods that use those uncertainties:

* **Random-effects group means** (DerSimonian-Laird): each group's mean weaning age
  allowing for real between-animal variation (τ²) on top of estimation error;
  a Q-test for any difference between groups and Holm-corrected pairwise z-tests.
* **Permutation test** on the point estimates: distribution-free check of whether
  group labels matter at all.
* **Hierarchical Bayesian model** (Gibbs sampler): specimen ages are partially
  pooled towards their group mean, giving shrunken specimen estimates, group
  posteriors and direct probabilities such as P(pig weaning earlier than cattle).
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy import stats

from .schema import EstimateRow

Z95 = 1.959964


class GroupEstimate(BaseModel):
    group: str
    n: int
    mean: float
    se: float
    ci_low: float
    ci_high: float
    tau: float = Field(description="Between-animal SD (months)")


class PairwiseTest(BaseModel):
    group_a: str
    group_b: str
    difference: float
    se: float
    z: float
    p: float
    p_holm: float


class BayesGroup(BaseModel):
    group: str
    n: int
    mean: float
    ci_low: float
    ci_high: float


class BayesPair(BaseModel):
    group_a: str
    group_b: str
    prob_a_earlier: float
    difference_mean: float
    difference_ci_low: float
    difference_ci_high: float


class BayesSpecimen(BaseModel):
    specimen_id: str
    group: str
    observed: float
    shrunk: float
    ci_low: float
    ci_high: float


class BayesResult(BaseModel):
    groups: list[BayesGroup]
    pairs: list[BayesPair]
    specimens: list[BayesSpecimen]
    tau_mean: float
    tau_ci_low: float
    tau_ci_high: float
    rhat_max: float
    draws: int


class GroupComparison(BaseModel):
    milestone: str
    model: str
    group_by: list[str]
    groups: list[GroupEstimate]
    q_between: float | None
    q_df: int
    q_p: float | None
    pairwise: list[PairwiseTest]
    permutation_p: float | None
    bayes: BayesResult | None
    notes: list[str] = Field(default_factory=list)


def _select(rows: list[EstimateRow], milestone: str, model: str | None, group_by: list[str]) -> pd.DataFrame:
    df = pd.DataFrame([r.model_dump() for r in rows])
    if df.empty:
        return df
    df = df[df["is_best"]] if model is None else df[df["model"] == model]
    df = df[df[milestone].notna()].copy()
    for g in group_by:
        df[g] = df[g].fillna("—")
    df["group"] = df[group_by].astype(str).agg(" · ".join, axis=1)
    # SE from the 95 % interval when available (completion only); otherwise unknown.
    if milestone == "completion":
        se = (df["completion_ci_high"] - df["completion_ci_low"]) / (2 * Z95)
    else:
        se = pd.Series(np.nan, index=df.index)
    df["se"] = se.where(se > 0)
    if df["se"].isna().any():
        fill = df["se"].median() if df["se"].notna().any() else max(df[milestone].std(ddof=1) / 4, 0.1)
        df["se"] = df["se"].fillna(fill if np.isfinite(fill) else 0.5)
    return df


def random_effects(y: np.ndarray, se: np.ndarray) -> tuple[float, float, float]:
    """DerSimonian-Laird pooled mean, its SE and τ."""
    w = 1 / se**2
    mu_fixed = np.sum(w * y) / np.sum(w)
    if y.size < 2:
        return float(y[0]), float(se[0]), 0.0
    q = np.sum(w * (y - mu_fixed) ** 2)
    c = np.sum(w) - np.sum(w**2) / np.sum(w)
    tau2 = max((q - (y.size - 1)) / c, 0.0) if c > 0 else 0.0
    w_star = 1 / (se**2 + tau2)
    mu = np.sum(w_star * y) / np.sum(w_star)
    return float(mu), float(math.sqrt(1 / np.sum(w_star))), float(math.sqrt(tau2))


def holm(p: list[float]) -> list[float]:
    order = np.argsort(p)
    adjusted = np.empty(len(p))
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (len(p) - rank) * p[idx]))
        adjusted[idx] = running
    return adjusted.tolist()


def permutation_test(y: np.ndarray, labels: np.ndarray, n_perm: int = 5000, seed: int = 0) -> float | None:
    """p-value for the between-group sum of squares under random relabelling."""
    groups = np.unique(labels)
    if groups.size < 2 or y.size <= groups.size:
        return None

    def ss_between(lab):
        return sum((lab == g).sum() * (y[lab == g].mean() - y.mean()) ** 2 for g in groups)

    observed = ss_between(labels)
    rng = np.random.default_rng(seed)
    hits = sum(ss_between(rng.permutation(labels)) >= observed - 1e-12 for _ in range(n_perm))
    return (hits + 1) / (n_perm + 1)


def hierarchical_bayes(
    y: np.ndarray, se: np.ndarray, groups: np.ndarray, *, chains: int = 4, iterations: int = 3000,
    burn: int = 1000, tau_scale: float = 3.0, prior_sd: float = 50.0, seed: int = 0,
) -> dict:
    """Gibbs sampler for  y_i ~ N(θ_i, se_i²),  θ_i ~ N(μ_g, τ²),  μ_g ~ N(ȳ, prior_sd²),
    τ ~ half-Cauchy(0, tau_scale)  (τ updated by Metropolis on log τ)."""
    names, gidx = np.unique(groups, return_inverse=True)
    G, n = names.size, y.size
    rng = np.random.default_rng(seed)
    m0 = float(y.mean())
    keep = iterations - burn
    mu_draws = np.empty((chains, keep, G))
    theta_draws = np.empty((chains, keep, n))
    tau_draws = np.empty((chains, keep))
    v_obs = se**2

    def log_post_tau(tau, theta, mu):
        if tau <= 0:
            return -np.inf
        resid = theta - mu[gidx]
        return (-n * math.log(tau) - 0.5 * np.sum(resid**2) / tau**2
                - math.log1p((tau / tau_scale) ** 2) + math.log(tau))  # + log-Jacobian

    for c in range(chains):
        tau = abs(rng.normal(1.0, 0.5)) + 0.1
        mu = np.array([y[gidx == g].mean() for g in range(G)]) + rng.normal(0, 0.5, G)
        theta = y.copy()
        step = 0.5
        for it in range(iterations):
            prec = 1 / v_obs + 1 / tau**2
            mean = (y / v_obs + mu[gidx] / tau**2) / prec
            theta = rng.normal(mean, 1 / np.sqrt(prec))
            for g in range(G):
                members = theta[gidx == g]
                p = members.size / tau**2 + 1 / prior_sd**2
                m = (members.sum() / tau**2 + m0 / prior_sd**2) / p
                mu[g] = rng.normal(m, 1 / math.sqrt(p))
            proposal = tau * math.exp(rng.normal(0, step))
            if math.log(rng.random()) < log_post_tau(proposal, theta, mu) - log_post_tau(tau, theta, mu):
                tau = proposal
            if it >= burn:
                k = it - burn
                mu_draws[c, k], theta_draws[c, k], tau_draws[c, k] = mu, theta, tau
    return {"names": names, "gidx": gidx, "mu": mu_draws, "theta": theta_draws, "tau": tau_draws}


def split_rhat(draws: np.ndarray) -> float:
    """Split-R̂ for an array of shape (chains, draws)."""
    half = draws.shape[1] // 2
    chains = np.concatenate([draws[:, :half], draws[:, half: 2 * half]])
    m, n = chains.shape
    within = chains.var(axis=1, ddof=1).mean()
    between = n * chains.mean(axis=1).var(ddof=1)
    if within <= 0:
        return 1.0
    return float(math.sqrt(((n - 1) / n * within + between / n) / within))


def compare_groups(
    rows: list[EstimateRow],
    *,
    group_by: list[str],
    milestone: str = "completion",
    model: str | None = None,
    bayes: bool = True,
    seed: int = 0,
) -> GroupComparison:
    df = _select(rows, milestone, model, group_by)
    label = model or "best (AICc)"
    result = GroupComparison(milestone=milestone, model=label, group_by=group_by, groups=[],
                             q_between=None, q_df=0, q_p=None, pairwise=[], permutation_p=None, bayes=None)
    if df.empty:
        result.notes.append("No estimates to compare")
        return result

    for name, sub in df.groupby("group"):
        mu, se, tau = random_effects(sub[milestone].to_numpy(float), sub["se"].to_numpy(float))
        result.groups.append(GroupEstimate(group=str(name), n=len(sub), mean=mu, se=se,
                                           ci_low=mu - Z95 * se, ci_high=mu + Z95 * se, tau=tau))
    if milestone != "completion":
        result.notes.append("Specimen uncertainties are only available for completion; a common SE was assumed")

    if len(result.groups) >= 2:
        means = np.array([g.mean for g in result.groups])
        w = 1 / np.array([g.se for g in result.groups]) ** 2
        pooled = np.sum(w * means) / np.sum(w)
        q = float(np.sum(w * (means - pooled) ** 2))
        result.q_between, result.q_df = q, len(result.groups) - 1
        result.q_p = float(stats.chi2.sf(q, result.q_df))
        pairs = list(itertools.combinations(result.groups, 2))
        raw = []
        for a, b in pairs:
            diff, se = a.mean - b.mean, math.hypot(a.se, b.se)
            z = diff / se if se > 0 else 0.0
            raw.append((a, b, diff, se, z, float(2 * stats.norm.sf(abs(z)))))
        for (a, b, diff, se, z, p), p_adj in zip(raw, holm([r[-1] for r in raw])):
            result.pairwise.append(PairwiseTest(group_a=a.group, group_b=b.group, difference=diff,
                                                se=se, z=z, p=p, p_holm=p_adj))
        result.permutation_p = permutation_test(df[milestone].to_numpy(float), df["group"].to_numpy(), seed=seed)
        if any(g.n < 3 for g in result.groups):
            result.notes.append("Some groups have fewer than 3 specimens; their means are poorly constrained")

    if bayes and len(df) >= 3:
        fit = hierarchical_bayes(df[milestone].to_numpy(float), df["se"].to_numpy(float),
                                 df["group"].to_numpy(), seed=seed)
        result.bayes = _summarise_bayes(fit, df, milestone)
        if result.bayes.rhat_max > 1.05:
            result.notes.append(f"Bayesian chains have not fully converged (R̂ = {result.bayes.rhat_max:.2f})")
    return result


def _summarise_bayes(fit: dict, df: pd.DataFrame, milestone: str) -> BayesResult:
    names, mu, theta, tau = fit["names"], fit["mu"], fit["theta"], fit["tau"]
    flat_mu = mu.reshape(-1, mu.shape[-1])
    flat_theta = theta.reshape(-1, theta.shape[-1])
    q = lambda a: (float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5)))
    groups = [
        BayesGroup(group=str(nm), n=int((fit["gidx"] == g).sum()), mean=float(flat_mu[:, g].mean()),
                   ci_low=q(flat_mu[:, g])[0], ci_high=q(flat_mu[:, g])[1])
        for g, nm in enumerate(names)
    ]
    pairs = []
    for a, b in itertools.combinations(range(len(names)), 2):
        d = flat_mu[:, a] - flat_mu[:, b]
        lo, hi = q(d)
        pairs.append(BayesPair(group_a=str(names[a]), group_b=str(names[b]),
                               prob_a_earlier=float(np.mean(d < 0)), difference_mean=float(d.mean()),
                               difference_ci_low=lo, difference_ci_high=hi))
    specimens = []
    for i, (_, row) in enumerate(df.iterrows()):
        lo, hi = q(flat_theta[:, i])
        specimens.append(BayesSpecimen(specimen_id=row["specimen_id"], group=row["group"],
                                       observed=float(row[milestone]), shrunk=float(flat_theta[:, i].mean()),
                                       ci_low=lo, ci_high=hi))
    rhat = max([split_rhat(tau)] + [split_rhat(mu[:, :, g]) for g in range(mu.shape[-1])])
    tlo, thi = q(tau.ravel())
    return BayesResult(groups=groups, pairs=pairs, specimens=specimens, tau_mean=float(tau.mean()),
                       tau_ci_low=tlo, tau_ci_high=thi, rhat_max=rhat, draws=int(tau.size))
