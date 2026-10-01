#!/usr/bin/env python
"""Calibrate per-mode relevance thresholds for memedb/relevance.py.

Workflow:
  1. `prepare`    - run a batch of queries through the real search path and
     write a labeling template CSV (top-10 candidates per query, `label`
     column blank) for a human to fill in.
  2. (human fills in the `label` column: 0 = unrelated, 1 = loosely
     relevant, 2 = strongly relevant - see scripts/CALIBRATION_README.md for
     the per-mode rubric)
  3. `calibrate`  - re-run the same queries, join the fresh cosine (and, for
     text, lexical coverage) against the filled-in labels, print cosine
     distributions by label, and suggest mid/high (/dup for image)
     thresholds.

This does not touch the live RRF ordering query in memedb/services/cosmos.py
- it calls search_hybrid/search_vector directly to read the raw `similarity`
(cosine) Cosmos already projects, the same value the app displays buckets
for.

Image-mode queries are always a corpus meme_id, not a file path - this lets
`calibrate` re-fetch the exact query image later (via Cosmos + Blob) no
matter which machine or session it runs on. The app's /calibrate admin page
produces labeled CSVs in this same shape directly; `prepare`/`--queries`
below is the batch/CLI alternative to that page.

Usage:
  python scripts/calibrate_thresholds.py prepare --mode text \
      --queries scripts/calibration_data/text_queries.csv \
      --out scripts/calibration_data/text_labels.csv

  # ... fill in the `label` column in text_labels.csv (or label in the app's
  # /calibrate page and export a CSV in the same shape) ...

  python scripts/calibrate_thresholds.py calibrate --mode text \
      --labels scripts/calibration_data/text_labels.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memedb.config import load_settings  # noqa: E402
from memedb.pipeline import blob_name_from_url, build_searchable_text  # noqa: E402
from memedb.relevance import lexical_coverage, tokenize  # noqa: E402
from memedb.services.blob import BlobService  # noqa: E402
from memedb.services.cosmos import CosmosService  # noqa: E402
from memedb.services.vision import VisionService  # noqa: E402

TOP_K = 10
LABEL_NAMES = {0: "unrelated", 1: "loosely relevant", 2: "strongly relevant"}


@dataclass
class Candidate:
    query_id: str
    query: str
    meme_id: str
    rank: int
    cosine: float
    coverage: float | None
    caption: str
    template_name: str


def _load_queries(path: Path, mode: str) -> list[tuple[str, str]]:
    """Returns [(query_id, query text or meme_id), ...]."""
    field = "query" if mode == "text" else "meme_id"
    with path.open(newline="", encoding="utf-8") as f:
        return [(row["query_id"], row[field]) for row in csv.DictReader(f)]


def _run_search(
    mode: str,
    query: str,
    vision_service: VisionService,
    cosmos_service: CosmosService,
    blob_service: BlobService,
) -> tuple[list[dict], set[str] | None]:
    if mode == "text":
        query_vector = vision_service.vectorize_text(query)
        words = query.split()[:10]
        results = cosmos_service.search_hybrid(query_vector, words, None, TOP_K)
        return results, tokenize(query)

    # Image queries are a meme_id in the corpus (never a file path or a
    # one-off upload), so the same query can always be re-fetched later -
    # see the module docstring.
    meme_id = query
    meme_doc = cosmos_service.get_by_id(meme_id)
    if meme_doc is None:
        raise ValueError(f"query image meme_id {meme_id!r} not found")
    data, _content_type = blob_service.download_image(blob_name_from_url(meme_doc["blobUrl"]))
    query_vector = vision_service.vectorize_image(data)
    results = cosmos_service.search_vector(query_vector, None, TOP_K)
    return results, None


def _to_candidates(query_id: str, query: str, results: list[dict], query_tokens: set[str] | None) -> list[Candidate]:
    candidates = []
    for rank, doc in enumerate(results, start=1):
        coverage = None
        if query_tokens is not None:
            doc_tokens = tokenize(
                build_searchable_text(doc.get("ocrText", ""), doc["caption"], doc["templateName"], doc["tags"])
            )
            coverage, _matched = lexical_coverage(query_tokens, doc_tokens)
        candidates.append(
            Candidate(
                query_id=query_id,
                query=query,
                meme_id=doc["id"],
                rank=rank,
                cosine=doc["similarity"],
                coverage=coverage,
                caption=doc.get("caption", ""),
                template_name=doc.get("templateName", ""),
            )
        )
    return candidates


def cmd_prepare(args: argparse.Namespace) -> int:
    settings = load_settings()
    vision_service = VisionService(settings)
    cosmos_service = CosmosService(settings)
    blob_service = BlobService(settings)

    queries = _load_queries(Path(args.queries), args.mode)
    rows: list[Candidate] = []
    for query_id, query in queries:
        results, query_tokens = _run_search(args.mode, query, vision_service, cosmos_service, blob_service)
        candidates = _to_candidates(query_id, query, results, query_tokens)
        rows.extend(candidates)
        print(f"{query_id}: {len(candidates)} candidates")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["query_id", "query", "rank", "meme_id", "caption", "templateName", "cosine", "label"])
        for c in rows:
            writer.writerow([c.query_id, c.query, c.rank, c.meme_id, c.caption, c.template_name, f"{c.cosine:.4f}", ""])

    print(f"\nwrote {len(rows)} candidate rows to {out_path}")
    print("Fill in the `label` column (0/1/2) - see scripts/CALIBRATION_README.md for the rubric.")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    settings = load_settings()
    vision_service = VisionService(settings)
    cosmos_service = CosmosService(settings)
    blob_service = BlobService(settings)

    with Path(args.labels).open(newline="", encoding="utf-8") as f:
        label_rows = list(csv.DictReader(f))

    if args.queries:
        queries = dict(_load_queries(Path(args.queries), args.mode))
    else:
        # The app's /calibrate page (and scripts/calibrate_thresholds.py
        # prepare) both write the query text/meme_id into every row, so a
        # separate --queries file is only needed if the labels CSV doesn't
        # carry it for some reason.
        queries = {}
        for row in label_rows:
            queries.setdefault(row["query_id"], row["query"])

    unlabeled = [r for r in label_rows if r["label"].strip() == ""]
    if unlabeled:
        print(f"warning: {len(unlabeled)} rows have no label yet, skipping them", file=sys.stderr)

    by_query: dict[str, list[Candidate]] = {}
    for query_id, query in queries.items():
        results, query_tokens = _run_search(args.mode, query, vision_service, cosmos_service, blob_service)
        by_query[query_id] = _to_candidates(query_id, query, results, query_tokens)

    samples = []  # each: {label, cosine, coverage, query_length}
    for row in label_rows:
        if row["label"].strip() == "":
            continue
        query_id, meme_id = row["query_id"], row["meme_id"]
        match = next((c for c in by_query.get(query_id, []) if c.meme_id == meme_id), None)
        if match is None:
            print(f"warning: {query_id}/{meme_id} not in current top-{TOP_K}, skipping", file=sys.stderr)
            continue
        samples.append(
            {
                "label": int(row["label"]),
                "cosine": match.cosine,
                "coverage": match.coverage,
                "query_length": len(queries[query_id].split()) if args.mode == "text" else 1,
            }
        )

    if not samples:
        print("no labeled samples matched a current search result - nothing to calibrate", file=sys.stderr)
        return 1

    _print_distribution(samples, args.mode)
    _suggest_thresholds(samples, args.mode)
    if args.logistic:
        _fit_logistic(samples, args.mode)
    _maybe_plot(samples, args.mode)
    return 0


def _print_distribution(samples: list[dict], mode: str) -> None:
    print(f"\n=== cosine distribution by label ({mode}) ===")
    for label in sorted({s["label"] for s in samples}):
        cosines = [s["cosine"] for s in samples if s["label"] == label]
        name = LABEL_NAMES.get(label, str(label))
        print(
            f"label {label} ({name}, n={len(cosines)}): "
            f"min={min(cosines):.3f} mean={statistics.mean(cosines):.3f} "
            f"median={statistics.median(cosines):.3f} max={max(cosines):.3f}"
        )


def _suggest_thresholds(samples: list[dict], mode: str) -> None:
    # Walk cosine cut points: "mid" is the lowest cut where results scoring
    # at or above it are relevant (label >= 1) at least half the time; "high"
    # is the lowest cut where they're strongly relevant (label == 2) at
    # least ~85% of the time.
    cuts = sorted({round(s["cosine"], 3) for s in samples})

    def relevant_rate(cut: float, min_label: int) -> float:
        at_or_above = [s for s in samples if s["cosine"] >= cut]
        if not at_or_above:
            return 0.0
        return sum(1 for s in at_or_above if s["label"] >= min_label) / len(at_or_above)

    mid = next((c for c in cuts if relevant_rate(c, 1) >= 0.5), None)
    high = next((c for c in cuts if relevant_rate(c, 2) >= 0.85), None)

    print(f"\n=== suggested thresholds ({mode}) ===")
    print(f"mid  (>=50% of results at/above this cosine are label>=1): {mid}")
    print(f"high (>=85% of results at/above this cosine are label==2): {high}")

    if mode == "image":
        dup_samples = [s["cosine"] for s in samples if s["label"] == 2]
        dup = min(dup_samples) if dup_samples else None
        print(f"dup  (min cosine among label==2 same-template pairs): {dup}")

    print(
        "\nThese are starting points, not final values - eyeball the "
        "distribution above (and the plot, if written) before committing "
        "them to TEXT_THRESHOLDS / IMAGE_THRESHOLDS in memedb/relevance.py, "
        "keyed by the current AZURE_VISION_MODEL_VERSION."
    )


def _fit_logistic(samples: list[dict], mode: str) -> None:
    """Pure-Python logistic regression fallback: P(label>=1) from
    (cosine, coverage, query_length). Optional - only useful if a single
    cosine cutoff doesn't cleanly separate relevant from irrelevant in the
    distribution printed above."""
    features = [
        (s["cosine"], s["coverage"] or 0.0, s["query_length"] / 10.0)
        for s in samples
    ]
    targets = [1.0 if s["label"] >= 1 else 0.0 for s in samples]

    weights = [0.0, 0.0, 0.0]
    bias = 0.0
    lr = 0.1
    n = len(features)

    for _ in range(2000):
        grad_w = [0.0, 0.0, 0.0]
        grad_b = 0.0
        for x, y in zip(features, targets):
            z = sum(w * xi for w, xi in zip(weights, x)) + bias
            pred = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            error = pred - y
            for i in range(3):
                grad_w[i] += error * x[i]
            grad_b += error
        weights = [w - lr * gw / n for w, gw in zip(weights, grad_w)]
        bias -= lr * grad_b / n

    print(f"\n=== logistic fallback ({mode}) ===")
    print(
        f"P(relevant) = sigmoid({weights[0]:.3f}*cosine + {weights[1]:.3f}*coverage "
        f"+ {weights[2]:.3f}*(query_words/10) + {bias:.3f})"
    )
    print("Use this only if the single-cutoff thresholds above mislabel too much of the distribution.")


def _maybe_plot(samples: list[dict], mode: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n(matplotlib not installed - skipping the distribution plot; `pip install matplotlib` for one)")
        return

    fig, ax = plt.subplots()
    for label in sorted({s["label"] for s in samples}):
        cosines = [s["cosine"] for s in samples if s["label"] == label]
        ax.hist(cosines, bins=20, alpha=0.5, label=f"label {label} ({LABEL_NAMES.get(label, label)})")
    ax.set_xlabel("cosine similarity")
    ax.set_ylabel("count")
    ax.set_title(f"{mode} search: cosine distribution by relevance label")
    ax.legend()

    out_path = Path("scripts/calibration_data") / f"{mode}_distribution.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    print(f"\nwrote distribution plot to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Run queries and write a labeling template CSV")
    prepare.add_argument("--mode", choices=["text", "image"], required=True)
    prepare.add_argument(
        "--queries", required=True, help="CSV with query_id,query (text mode) or query_id,meme_id (image mode)"
    )
    prepare.add_argument("--out", required=True, help="Where to write the labeling template CSV")
    prepare.set_defaults(func=cmd_prepare)

    calibrate = subparsers.add_parser("calibrate", help="Compute suggested thresholds from filled-in labels")
    calibrate.add_argument("--mode", choices=["text", "image"], required=True)
    calibrate.add_argument(
        "--queries",
        required=False,
        default=None,
        help="Optional - only needed if --labels doesn't already carry the query text/meme_id per row",
    )
    calibrate.add_argument("--labels", required=True, help="The labeling template CSV with `label` filled in")
    calibrate.add_argument(
        "--logistic", action="store_true", help="Also fit the optional logistic-regression fallback"
    )
    calibrate.set_defaults(func=cmd_calibrate)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
