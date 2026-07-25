"""Hybrid scoring for PR <-> tracker matching.

Granite content similarity (cosine) stays the base ranker. On top of it we add
cheap, high-precision *structural* signals as bounded boosts/penalties:

  * branch number  -- the issue's tracker number appears in the PR's head branch
                      (e.g. ``wip-46912-...``). Near-decisive.
  * component      -- the PR and the issue point at the same Ceph subsystem
                      (rbd, rados, cephfs, bluestore, rgw, ...). Same -> small
                      boost; clearly different -> penalty. This kills the most
                      common false positive: a semantically-so-so PR from an
                      unrelated area.

Ceph is a monorepo, so a PR's component isn't a field -- we infer it from the
title prefix ("rbd-mirror: ...") and the head branch. Weights are env-tunable
and can be validated against real ``#ref`` links with scripts/eval_linkage.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import get_settings

_TOKEN = re.compile(r"[a-z0-9-]+")
_NUM = re.compile(r"\d{4,}")

# Ceph subsystem -> keywords that indicate it, whether in a PR title prefix /
# branch or a Redmine project name.
_ALIASES: dict[str, set[str]] = {
    "rbd": {"rbd", "librbd", "rbd-mirror"},
    "rados": {"rados", "osd", "mon", "monitor", "objecter", "crush", "pg"},
    "cephfs": {"cephfs", "mds", "ceph-fuse", "kclient", "fscrypt", "fuse", "fs"},
    "bluestore": {"bluestore", "bluefs", "objectstore", "rocksdb", "kv"},
    "rgw": {"rgw", "radosgw", "s3", "swift"},
    "mgr": {"mgr", "ceph-mgr", "prometheus", "restful"},
    "dashboard": {"dashboard"},
    "orchestrator": {"orch", "cephadm", "rook", "orchestrator"},
    "crimson": {"crimson", "seastar", "seastore"},
    "nvmeof": {"nvme", "nvmeof", "nvme-of"},
    "devops": {"build", "packaging", "deb", "rpm", "cmake", "jenkins", "teuthology", "qa"},
    "doc": {"doc", "docs", "documentation"},
}


@dataclass
class Weights:
    branch: float
    component: float
    component_penalty: float


def get_weights() -> Weights:
    s = get_settings()
    return Weights(
        branch=s.hybrid_branch_weight,
        component=s.hybrid_component_weight,
        component_penalty=s.hybrid_component_penalty,
    )


def _tokens(text: str | None) -> set[str]:
    return set(_TOKEN.findall((text or "").lower()))


def _canonicals(tokens: set[str]) -> set[str]:
    return {canon for canon, kws in _ALIASES.items() if tokens & kws}


def components_for(name: str | None) -> set[str]:
    """Canonical Ceph subsystem(s) implied by a project/component name."""
    return _canonicals(_tokens(name))


def pr_components(pr) -> set[str]:
    """Infer a PR's Ceph subsystem(s) from its title prefix and head branch."""
    prefix = (getattr(pr, "title", "") or "").split(":", 1)[0]
    return _canonicals(_tokens(prefix) | _tokens(getattr(pr, "head_branch", None)))


def issue_components(issue) -> set[str]:
    """Infer an issue's subsystem(s) from its Redmine project name."""
    return components_for(getattr(issue, "project_name", None))


def component_relation(pr, issue) -> int:
    """1 = same component, -1 = clearly different, 0 = unknown on either side."""
    pc, ic = pr_components(pr), issue_components(issue)
    if not pc or not ic:
        return 0
    return 1 if (pc & ic) else -1


def branch_matches_issue(pr, issue) -> bool:
    """True if the issue's tracker number is encoded in the PR's head branch."""
    branch = getattr(pr, "head_branch", None)
    if not branch or getattr(issue, "id", None) is None:
        return False
    return issue.id in {int(x) for x in _NUM.findall(branch)}


def structural_bonus(pr, issue, weights: Weights | None = None) -> float:
    """Additive bonus (can be negative) to combine with content cosine."""
    w = weights or get_weights()
    bonus = 0.0
    if branch_matches_issue(pr, issue):
        bonus += w.branch
    rel = component_relation(pr, issue)
    if rel > 0:
        bonus += w.component
    elif rel < 0:
        bonus -= w.component_penalty
    return bonus


def hybrid_score(cosine: float, pr, issue, weights: Weights | None = None) -> float:
    """Content cosine plus structural bonus -- the value we rank/threshold on."""
    return cosine + structural_bonus(pr, issue, weights)
