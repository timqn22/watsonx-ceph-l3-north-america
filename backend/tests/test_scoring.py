"""Hybrid scoring signals: component agreement and branch-number match."""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.scoring import (
    Weights,
    branch_matches_issue,
    component_relation,
    structural_bonus,
)


def _pr(title="", head_branch=""):
    return SimpleNamespace(title=title, head_branch=head_branch)


def _issue(id_=1, project_name=None):
    return SimpleNamespace(id=id_, project_name=project_name)


def test_component_same_and_cross():
    # "rbd-mirror:" prefix -> rbd; issue project RBD -> rbd -> same.
    assert component_relation(_pr("rbd-mirror: fix replayer"), _issue(project_name="rbd")) == 1
    # osd PR vs CephFS issue -> different components.
    assert component_relation(_pr("osd: fix recovery"), _issue(project_name="CephFS")) == -1
    # Unknown on one side -> neutral.
    assert component_relation(_pr("misc cleanup"), _issue(project_name="rbd")) == 0


def test_branch_number_match():
    assert branch_matches_issue(_pr(head_branch="wip-46912-fix"), _issue(id_=46912))
    assert not branch_matches_issue(_pr(head_branch="wip-rbd-fix"), _issue(id_=46912))
    assert not branch_matches_issue(_pr(head_branch=""), _issue(id_=46912))


def test_structural_bonus_signs():
    w = Weights(branch=0.2, component=0.05, component_penalty=0.1)
    # same component + branch match (5-digit tracker id) -> both boosts
    b = structural_bonus(
        _pr("rbd: x", "wip-74854-y"), _issue(id_=74854, project_name="rbd"), w
    )
    assert abs(b - 0.25) < 1e-9
    # cross component, no branch -> penalty
    b2 = structural_bonus(
        _pr("osd: x", "wip-y"), _issue(id_=74854, project_name="CephFS"), w
    )
    assert abs(b2 + 0.1) < 1e-9
    # unknown component, no branch -> zero
    assert structural_bonus(
        _pr("misc", ""), _issue(id_=74854, project_name="Performance"), w
    ) == 0.0
