"""Evaluate PR <-> tracker matching accuracy against existing #ref links.

Ground truth = PRs whose body references a tracker we've scraped. For each, we
check whether the matcher ranks the *true* issue #1 (or in the top 3), using
content-only cosine vs the hybrid score (content + structural signals). This
turns "which weighting is better?" into a number on your own data.

Run it after a scrape, from the backend/ directory:

    python scripts/eval_linkage.py

Tune by setting the HYBRID_* env vars and re-running, e.g.:

    HYBRID_COMPONENT_PENALTY=0.15 python scripts/eval_linkage.py

Memory: embeddings are streamed out of SQLite and converted straight to a
compact float32 matrix (the source Python lists are dropped as we go), and only
ground-truth PRs are kept, so this stays flat even at 60k+ issues / 70k+ PRs.
"""

from __future__ import annotations

import os
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.ai.reranker import get_reranker  # noqa: E402
from app.ai.scoring import _ALIASES, get_weights, issue_components, pr_components  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Issue, PullRequest  # noqa: E402
from app.text import issue_embed_text, pr_embed_text  # noqa: E402

_NUM = re.compile(r"\d{4,}")


def main() -> None:
    init_db()
    w = get_weights()
    reranker = get_reranker()
    want_text = reranker.enabled  # only hold subject/description/body if reranking
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

        # --- Stream issues into a preallocated float32 matrix -----------------
        # Each row's JSON-parsed list is copied into the matrix and then dropped,
        # so we never hold 60k+ Python float-lists at once.
        issue_ids_l: list[int] = []
        issue_masks_l: list[int] = []
        issue_texts: list[str] = []  # only filled when reranking
        issue_mat: np.ndarray | None = None
        cols = (Issue.id, Issue.embedding, Issue.project_name, Issue.subject, Issue.description)
        for row in s.execute(
            select(*cols).where(Issue.embedding.is_not(None))
        ).yield_per(2000):
            iid, emb, project, subject, desc = row
            if issue_mat is None:
                issue_mat = np.empty((n_issues, len(emb)), dtype=np.float32)
            issue_mat[len(issue_ids_l)] = emb
            issue_ids_l.append(iid)
            issue_masks_l.append(mask(issue_components(SimpleNamespace(project_name=project))))
            if want_text:
                issue_texts.append(issue_embed_text(subject or "", desc))

        # Some rows may have been added/removed mid-run; trim to what we saw.
        got = len(issue_ids_l)
        issue_mat = issue_mat[:got]
        issue_ids = np.asarray(issue_ids_l, dtype=np.int64)
        issue_masks = np.asarray(issue_masks_l, dtype=np.int64)
        id_to_idx = {iid: k for k, iid in enumerate(issue_ids_l)}
        idset = set(issue_ids_l)
        issue_matT = np.ascontiguousarray(issue_mat.T)  # (d, N)

        # --- Stream PRs, keeping only ground-truth (references a scraped issue) ---
        gt_emb: list[np.ndarray] = []
        gt_true_idx: list[list[int]] = []
        gt_mask: list[int] = []
        gt_bnums: list[list[int]] = []
        gt_text: list[str] = []  # only filled when reranking
        pcols = (
            PullRequest.embedding,
            PullRequest.title,
            PullRequest.head_branch,
            PullRequest.body,
            PullRequest.referenced_issue_ids,
        )
        for emb, title, branch, body, refs in s.execute(
            select(*pcols).where(PullRequest.embedding.is_not(None))
        ).yield_per(2000):
            trues = [i for i in (refs or []) if i in idset]
            if not trues:
                continue
            gt_emb.append(np.asarray(emb, dtype=np.float32))
            gt_true_idx.append([id_to_idx[t] for t in trues])
            ns = SimpleNamespace(title=title, head_branch=branch)
            gt_mask.append(mask(pr_components(ns)))
            gt_bnums.append([int(x) for x in _NUM.findall(branch or "")])
            if want_text:
                gt_text.append(pr_embed_text(title or "", body))

        if not gt_emb:
            print("No ground-truth links (no scraped PR references a scraped issue).")
            print("Tip: scrape GitHub PRs and make sure the referenced issues are in the DB.")
            return

        pr_mat = np.asarray(gt_emb, dtype=np.float32)
        pr_masks = np.asarray(gt_mask, dtype=np.int64)
        n = len(gt_emb)

        def evaluate(hybrid: bool) -> tuple[float, float, float]:
            top1 = top3 = 0
            rr = 0.0
            batch = 256
            for start in range(0, n, batch):
                sl = slice(start, start + batch)
                scores = pr_mat[sl] @ issue_matT  # (b, N) cosine
                if hybrid:
                    pm = pr_masks[sl][:, None]
                    same = (issue_masks[None, :] & pm) != 0
                    both = (issue_masks[None, :] != 0) & (pm != 0)
                    scores = scores + np.where(
                        same, w.component, np.where(both, -w.component_penalty, 0.0)
                    ).astype(np.float32)
                    for bi in range(scores.shape[0]):
                        bnums = gt_bnums[start + bi]
                        if bnums:
                            scores[bi] += np.where(
                                np.isin(issue_ids, bnums), w.branch, 0.0
                            ).astype(np.float32)
                for bi in range(scores.shape[0]):
                    row = scores[bi]
                    tidx = gt_true_idx[start + bi]
                    ts = row[tidx].max()
                    # 0-based rank = how many issues score strictly higher. Real
                    # Granite scores don't tie, so this is exact; only synthetic
                    # identical-text data produces ties (counted optimistically).
                    rank = int((row > ts).sum())
                    top1 += rank == 0
                    top3 += rank < 3
                    rr += 1.0 / (rank + 1)
            return top1 / n, top3 / n, rr / n

        print("scoring content-only ...")
        c1, c3, cmrr = evaluate(False)
        print("scoring hybrid ...")
        h1, h3, hmrr = evaluate(True)

        print(f"Ground-truth links evaluated: {n}  (issues in pool: {got})")
        print(
            f"Weights: branch={w.branch} component={w.component} "
            f"penalty={w.component_penalty}"
        )
        print(f"{'':16}{'top-1':>8}{'top-3':>8}{'MRR':>8}")
        print(f"{'content-only':16}{c1:>7.1%}{c3:>8.1%}{cmrr:>8.3f}")
        print(f"{'hybrid':16}{h1:>7.1%}{h3:>8.1%}{hmrr:>8.3f}")
        print(f"{'delta':16}{h1 - c1:>+7.1%}{h3 - c3:>+8.1%}{hmrr - cmrr:>+8.3f}")

        # Cross-encoder rerank of the content top-K (only when enabled).
        #
        # Unlike the vectorized passes above, this is one model call per
        # (link x candidate) pair -- ~850k inferences over the full set on CPU.
        # So by default we estimate it from a random sample; set
        # EVAL_RERANK_SAMPLE=0 to score every link. The hybrid row above is the
        # baseline to beat, so we recompute hybrid on the SAME sample for an
        # apples-to-apples "delta vs hybrid".
        if reranker.enabled:
            sample = int(os.environ.get("EVAL_RERANK_SAMPLE", "3000"))
            if sample and sample < n:
                idx = np.random.default_rng(0).choice(n, size=sample, replace=False)
                note = f" (random sample of {sample} of {n} links)"
            else:
                idx = np.arange(n)
                note = ""
            print(f"\nreranking with {reranker.model_id}{note} ...")
            k = get_settings().rerank_top_k
            top1 = top3 = 0
            rr = 0.0
            h1s = h3s = 0
            hmrrs = 0.0
            for pi in idx:
                pi = int(pi)
                content = issue_mat @ pr_mat[pi]
                # Hybrid score on the same sample, for a fair baseline.
                hybrid = content + np.where(
                    (issue_masks & gt_mask[pi]) != 0,
                    w.component,
                    np.where((issue_masks != 0) & (gt_mask[pi] != 0), -w.component_penalty, 0.0),
                ).astype(np.float32)
                if gt_bnums[pi]:
                    hybrid = hybrid + np.where(
                        np.isin(issue_ids, gt_bnums[pi]), w.branch, 0.0
                    ).astype(np.float32)
                tidx = gt_true_idx[pi]
                hts = hybrid[tidx].max()
                hrank = int((hybrid > hts).sum())
                h1s += hrank == 0
                h3s += hrank < 3
                hmrrs += 1.0 / (hrank + 1)
                # Rerank the content top-K pool with the cross-encoder.
                pool = np.argsort(-content)[:k]
                rs = reranker.scores(gt_text[pi], [issue_texts[p] for p in pool])
                reranked = [int(pool[i]) for i in sorted(range(len(pool)), key=lambda i: -rs[i])]
                best = k  # true issue not in the recalled top-K -> a miss
                for ti in tidx:
                    if ti in reranked:
                        best = min(best, reranked.index(ti))
                top1 += best == 0
                top3 += best < 3
                rr += 1.0 / (best + 1)
            m = len(idx)
            r1, r3, rmrr = top1 / m, top3 / m, rr / m
            sh1, sh3, shmrr = h1s / m, h3s / m, hmrrs / m
            print(f"{'':16}{'top-1':>8}{'top-3':>8}{'MRR':>8}")
            print(f"{'hybrid (sample)':16}{sh1:>7.1%}{sh3:>8.1%}{shmrr:>8.3f}")
            print(f"{'hybrid+rerank':16}{r1:>7.1%}{r3:>8.1%}{rmrr:>8.3f}")
            print(f"{'delta vs hybrid':16}{r1 - sh1:>+7.1%}{r3 - sh3:>+8.1%}{rmrr - shmrr:>+8.3f}")


if __name__ == "__main__":
    main()
