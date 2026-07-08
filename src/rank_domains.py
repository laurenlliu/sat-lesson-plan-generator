"""
Ranks a student's content domains by priority for tutoring focus.

College Board reports give a performance band per domain (e.g.
420-480 on a 200-800 scaled section) rather than a raw accuracy
percentage. We combine two signals to prioritize domains:

  1. How low the performance band sits (weaker band = higher priority)
  2. How much weight that domain carries in its section (higher weight
     = mistakes there cost more, so fixing it matters more)

If two reports are supplied for the same student, we also compute
per-domain movement between them, so the plan can call out
improvement or decline alongside the current weak areas.
"""

from typing import Optional

SECTION_SCALE_MAX = 800
SECTION_SCALE_MIN = 200


def _band_strength(perf_low: int, perf_high: int) -> float:
    """Returns 0-1, where 0 = weakest possible band, 1 = strongest."""
    midpoint = (perf_low + perf_high) / 2
    return (midpoint - SECTION_SCALE_MIN) / (SECTION_SCALE_MAX - SECTION_SCALE_MIN)


def rank_domains(domains: list, previous_domains: Optional[list] = None) -> list:
    """
    domains: list of dicts from extract_report (current/most recent test)
    previous_domains: optional list of dicts from an earlier test, for
                       the same student, to compute movement

    Returns domains sorted by priority (highest priority first), each
    annotated with a `priority_score` and, if available, `change`
    (points the band midpoint moved since the previous test).
    """
    previous_by_name = {d["name"]: d for d in (previous_domains or [])}

    ranked = []
    for d in domains:
        strength = _band_strength(d["perf_low"], d["perf_high"])
        weakness = 1 - strength
        # Weight is 0-35ish (%), normalize to 0-1 by dividing by 35.
        weight_factor = min(d["weight_pct"] / 35.0, 1.0)
        priority_score = round((weakness * 0.65 + weight_factor * 0.35) * 100, 1)

        entry = dict(d)
        entry["priority_score"] = priority_score

        prev = previous_by_name.get(d["name"])
        if prev:
            prev_mid = (prev["perf_low"] + prev["perf_high"]) / 2
            curr_mid = (d["perf_low"] + d["perf_high"]) / 2
            entry["change"] = round(curr_mid - prev_mid, 1)

        ranked.append(entry)

    ranked.sort(key=lambda d: d["priority_score"], reverse=True)
    return ranked


if __name__ == "__main__":
    import sys
    import json
    from extract_report import extract_report, asdict

    if len(sys.argv) not in (2, 3):
        print("Usage: python rank_domains.py current_report.pdf [previous_report.pdf]")
        sys.exit(1)

    current = extract_report(sys.argv[1])
    previous = extract_report(sys.argv[2]) if len(sys.argv) == 3 else None

    ranked = rank_domains(
        current.domains,
        previous.domains if previous else None,
    )
    print(json.dumps(ranked, indent=2))
