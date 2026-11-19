"""Fit score weights to the user's own judgement.

Labels live in <workspace>/data/labels.jsonl: one listing per line with the user's rating
(strong | maybe | no) and the full job text, so tuning re-scores with the *current* profile.

Objective: pairwise ranking accuracy. For every pair of listings with different ratings,
the higher-rated one should score higher. Ties are broken by average margin, then by staying
close to the current weights. Search: hill-climb moving 0.05 of weight between components.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from itertools import permutations

from . import workspace
from .matcher import score_job
from .models import Job

RATING = {"strong": 1.0, "maybe": 0.5, "no": 0.0}
STEP = 0.05


def labels_path():
    return workspace.path("data", "labels.jsonl")


def last_scan_path():
    return workspace.path("data", "last_scan.json")


def save_scan(results) -> None:
    rows = [{"job": _job_dict(r.job), "score": r.score, "breakdown": r.breakdown,
             "matched": r.matched_skills, "missing": r.missing_skills} for r in results]
    p = last_scan_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, indent=1), encoding="utf-8")


def _job_dict(j: Job) -> dict:
    d = asdict(j)
    d["posted"] = j.posted.isoformat() if j.posted else None
    return d


def _job(d: dict) -> Job:
    d = dict(d)
    d["posted"] = datetime.fromisoformat(d["posted"]) if d.get("posted") else None
    return Job(**d)


def add_label(job_id: str, rating: str, note: str = "") -> str:
    rating = rating.lower()
    if rating not in RATING:
        raise ValueError(f"rating must be one of {list(RATING)}")
    rows = json.loads(last_scan_path().read_text(encoding="utf-8")) if last_scan_path().exists() else []
    match = next((r for r in rows if r["job"]["id"] == job_id), None)
    if not match:
        raise ValueError(f"{job_id} not in data/last_scan.json; run `scan --save` first")
    existing = [json.loads(l) for l in labels_path().read_text(encoding="utf-8").splitlines()] \
        if labels_path().exists() else []
    existing = [e for e in existing if e["job"]["id"] != job_id]       # re-rating replaces
    existing.append({"rating": rating, "note": note, "job": match["job"]})
    labels_path().write_text("\n".join(json.dumps(e) for e in existing) + "\n", encoding="utf-8")
    return f"{rating}: {match['job']['title']} @ {match['job']['company']} ({len(existing)} labels total)"


def _evaluate(weights, items):
    """items: list of (rating, breakdown). Returns (accuracy, mean_margin, n_pairs)."""
    scores = [(r, sum(weights[k] * b.get(k, 0) for k in weights)) for r, b in items]
    good = pairs = 0
    margin = 0.0
    for (ra, sa), (rb, sb) in permutations(scores, 2):
        if ra > rb:
            pairs += 1
            if sa > sb:
                good += 1
                margin += sa - sb
    return (good / pairs if pairs else 0.0), (margin / pairs if pairs else 0.0), pairs


def fit(profile, settings, aliases) -> dict:
    if "_vocab" not in settings:
        from .profile import load_vocab
        settings = {**settings, "_vocab": load_vocab()}
    rows = [json.loads(l) for l in labels_path().read_text(encoding="utf-8").splitlines() if l.strip()] \
        if labels_path().exists() else []
    if len({r["rating"] for r in rows}) < 2:
        raise ValueError("Need listings rated with at least two different ratings to tune.")
    items, scored = [], []
    for r in rows:
        res = score_job(profile, _job(r["job"]), settings["weights"], aliases,
                        vocab=settings.get("_vocab"), fit=settings.get("fit"))
        items.append((RATING[r["rating"]], res.breakdown))
        scored.append((r["rating"], res))

    current = {k: float(v) for k, v in settings["weights"].items()}
    key = lambda w: (*_evaluate(w, items)[:2], -sum(abs(w[k] - current[k]) for k in w))
    best, best_key = dict(current), key(current)
    improved = True
    while improved:
        improved = False
        for a, b in permutations(best, 2):
            if best[a] < STEP - 1e-9:
                continue
            cand = dict(best)
            cand[a] = round(cand[a] - STEP, 2)
            cand[b] = round(cand[b] + STEP, 2)
            k = key(cand)
            if k > best_key:
                best, best_key, improved = cand, k, True

    before_acc, _, pairs = _evaluate(current, items)
    after_acc = best_key[0]
    new_scores = [(rt, 100 * sum(best[k] * res.breakdown[k] for k in best)) for rt, res in scored]
    threshold = _suggest_threshold(new_scores)
    return {"current": current, "suggested": best, "pairs": pairs, "labels": len(rows),
            "accuracy_before": before_acc, "accuracy_after": after_acc,
            "suggested_min_match_score": threshold,
            "per_listing": [(rt, res.job.title, res.job.company, res.score,
                             round(100 * sum(best[k] * res.breakdown[k] for k in best), 1))
                            for rt, res in scored]}


def _suggest_threshold(scores) -> int | None:
    """Integer cut that best keeps 'strong' at/above and 'no' below; 'maybe' is ignored."""
    strong = [s for r, s in scores if r == "strong"]
    no = [s for r, s in scores if r == "no"]
    if not strong or not no:
        return None
    best_t, best_ok = None, -1
    for t in range(0, 101):
        ok = sum(s >= t for s in strong) + sum(s < t for s in no)
        if ok > best_ok or (ok == best_ok and best_t is not None and abs(t - 60) < abs(best_t - 60)):
            best_t, best_ok = t, ok
    return best_t


def apply_weights(weights: dict) -> None:
    """Write weights into the workspace's config/settings.yaml, keeping other keys."""
    import yaml
    p = workspace.path("config", "settings.yaml")
    data = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}
    data["weights"] = {k: round(v, 2) for k, v in weights.items()}
    header = "# Overrides for the engine's defaults. Weights last set by `gighunter tune --apply`.\n"
    p.write_text(header + yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
