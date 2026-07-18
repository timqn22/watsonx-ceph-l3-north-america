"""Grid-search the hybrid structural weights against your real #ref links.

The hybrid score is Granite cosine plus three hand-set structural weights:

    branch    -- issue's tracker number is in the PR's head branch
    component -- PR and issue point at the same Ceph subsystem
    penalty   -- ... or clearly different subsystems (subtracted)

This sweeps combinations of those three and reports the top-1 / MRR for each, so
you can pick the optimum for your data. It is FREE -- no re-embedding, no
re-scraping -- and reuses the same ground truth as scripts/eval_linkage.py.

    python scripts/tune_weights.py

Cosine is computed once per PR batch and reused across every weight combo, so the
whole grid costs about one eval run. Override the grids with env vars, e.g.:

    BRANCH_GRID=0.15,0.2,0.25 COMPONENT_GRID=0.05,0.08 python scripts/tune_weights.py
"""

from __future__ import annotations

import os
import re
import sys
from itertools import product
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.ai.scoring import _ALIASES, get_weights, issue_components, pr_components  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Issue, PullRequest  # noqa: E402

_NUM = re.compile(r"\d{4,}")


def _grid(name: str, default: list[float]) -> list[float]:
    raw = os.environ.get(name)
    return [float(x) for x in raw.split(",")] if raw else default


def main() -> None:
    init_db()
    bit = {c: i for i, c in enumerate(_ALIASES)}

    def mask(components: set[str]) -> int:
        m = 0
        for c in components:
            m |= 1 << bit[c]
        return m

    with SessionLocal() as s:
        n_issues = s.scalar(
            select(func.count()).select_from(Issue).where(Issue.embedding.is_not(None))
        )
        if not n_issues:
            print("No embedded issues. Run a scrape + embed first.")
            return

        issue_ids_l: list[int] = []
        issue_masks_l: list[int] = []
        issue_mat: np.ndarray | None = None
        for iid, emb, project in s.execute(
            select(Issue.id, Issue.embedding, Issue.project_name).where(
                Issue.embedding.is_not(None)
            )
        ).yield_per(2000):
            if issue_mat is None:
                issue_mat = np.empty((n_issues, len(emb)), dtype=np.float32)
            issue_mat[len(issue_ids_l)] = emb
            issue_ids_l.append(iid)
            issue_masks_l.append(mask(issue_components(SimpleNamespace(project_name=project))))
        got = len(issue_ids_l)
        issue_mat = issue_mat[:got]
        issue_ids = np.asarray(issue_ids_l, dtype=np.int64)
        issue_masks = np.asarray(issue_masks_l, dtype=np.int64)
        id_to_idx = {iid: k for k, iid in enumerate(issue_ids_l)}
        idset = set(issue_ids_l)
        issue_matT = np.ascontiguousarray(issue_mat.T)

        gt_emb: list[np.ndarray] = []
        gt_true_idx: list[list[int]] = []
        gt_mask: list[int] = []
        gt_bnums: list[list[int]] = []
        for emb, title, branch, refs in s.execute(
            select(
                PullRequest.embedding, PullRequest.title,
                PullRequest.head_branch, PullRequest.referenced_issue_ids,
            ).where(PullRequest.embedding.is_not(None))
        ).yield_per(2000):
            trues = [i for i in (refs or []) if i in idset]
            if not trues:
                continue
            gt_emb.append(np.asarray(emb, dtype=np.float32))
            gt_true_idx.append([id_to_idx[t] for t in trues])
            gt_mask.append(mask(pr_components(SimpleNamespace(title=title, head_branch=branch))))
            gt_bnums.append([int(x) for x in _NUM.findall(branch or "")])
        if not gt_emb:
            print("No ground-truth links found.")
            return

        pr_mat = np.asarray(gt_emb, dtype=np.float32)
        pr_masks = np.asarray(gt_mask, dtype=np.int64)
        n = len(gt_emb)

    branch_grid = _grid("BRANCH_GRID", [0.1, 0.2, 0.3])
    comp_grid = _grid("COMPONENT_GRID", [0.03, 0.05, 0.08])
    pen_grid = _grid("PENALTY_GRID", [0.05, 0.1, 0.15])
    combos = list(product(branch_grid, comp_grid, pen_grid))
    print(f"Sweeping {len(combos)} weight combos over {n} links "
          f"(issues in pool: {got}) ...")

    top1 = np.zeros(len(combos))
    mrr = np.zeros(len(combos))
    batch = 256
    for start in range(0, n, batch):
        chunk = list(range(start, min(start + batch, n)))
        cosine = pr_mat[chunk] @ issue_matT  # (b, N), reused across combos
        pm = pr_masks[chunk][:, None]
        same = (issue_masks[None, :] & pm) != 0
        both = (issue_masks[None, :] != 0) & (pm != 0)
        pen_mask = both & ~same
        branch_bonus = np.zeros_like(cosine)
        for bi, ridx in enumerate(chunk):
            if gt_bnums[ridx]:
                branch_bonus[bi] = np.isin(issue_ids, gt_bnums[ridx])
        for ci, (bw, cw, pw) in enumerate(combos):
            scores = cosine + cw * same - pw * pen_mask + bw * branch_bonus
            for bi, ridx in enumerate(chunk):
                row = scores[bi]
                ts = row[gt_true_idx[ridx]].max()
                rank = int((row > ts).sum())
                top1[ci] += rank == 0
                mrr[ci] += 1.0 / (rank + 1)

    top1 /= n
    mrr /= n
    cur = get_weights()
    order = np.argsort(-top1)
    print(f"\n{'branch':>7}{'comp':>7}{'penalty':>9}{'top-1':>9}{'MRR':>8}")
    for ci in order:
        bw, cw, pw = combos[ci]
        star = "  <- current" if (bw, cw, pw) == (cur.branch, cur.component, cur.component_penalty) else ""
        print(f"{bw:>7.2f}{cw:>7.2f}{pw:>9.2f}{top1[ci]:>8.1%}{mrr[ci]:>8.3f}{star}")
    best = order[0]
    bw, cw, pw = combos[best]
    print(f"\nBest: branch={bw} component={cw} penalty={pw}  "
          f"(top-1 {top1[best]:.1%}).  Set with env vars to lock it in:")
    print(f"  HYBRID_BRANCH_WEIGHT={bw} HYBRID_COMPONENT_WEIGHT={cw} "
          f"HYBRID_COMPONENT_PENALTY={pw}")


if __name__ == "__main__":
    main()
