# Calibrating relevance thresholds

Calibration produces `mid`/`high`/`dup` cosine cutoffs for
`memedb/relevance.py`'s bucket labels (`weak`/`possible`/`strong` for text
search, `weak`/`loose`/`similar`/`near_duplicate` for image search). Until
you run this, the app uses clearly-marked provisional placeholder thresholds
and logs a warning on startup and on first search.

Two ways to label: the **`/calibrate` admin page** (recommended — see
thumbnails while scoring) or the **CLI script** (batch/scriptable). Both
produce the same CSV shape and feed the same `calibrate` step.

## Option A: the `/calibrate` page (recommended)

Sign in as an admin and open `/calibrate`. For each query:

1. **Text mode**: type a query, click Run.
2. **Image mode**: pick an existing meme from the corpus as the query image
   (there's no raw-upload option here — calibration always references a real
   meme_id, so the exact query image can be re-fetched later; see "why
   meme_id, not a file" below).
3. Score each result 0/1/2 using the rubric below.

Labels accumulate in the page (autosaved to `localStorage` so a reload
doesn't lose progress) across as many queries as you want. When you're done
(or periodically, as a checkpoint), click **Export CSV** — this downloads
`text_labels.csv` or `image_labels.csv` in the exact shape
`calibrate_thresholds.py` expects. **Import CSV** re-loads a previously
exported file so you can resume a session or merge labels done on another
device; rows are merged by `(query_id, meme_id)`, with the imported copy
winning on conflicts.

Then skip to [Calibrate](#calibrate) below.

## Option B: the CLI script (batch/scriptable)

### 1. Prepare the query set

Two starter files are provided:

- `scripts/calibration_data/text_queries.csv` - ~45 example text queries,
  mixing literal meme names ("drake pointing", "distracted boyfriend") with
  abstract/vibe queries ("monday energy", "when the code finally works").
  Edit this to better match what your users actually search for.
- `scripts/calibration_data/image_queries.csv` - a template with
  `query_id,meme_id` columns. Replace the placeholder rows with ~30 real
  meme IDs from your own corpus (aim for a spread across categories and
  templates, plus a few near-duplicates/reuploads of the same template if
  you have any, since those anchor the `dup` threshold). Pull IDs via
  `GET /memes` or by browsing the app.

### 2. Generate the labeling sheet

```
python scripts/calibrate_thresholds.py prepare --mode text \
    --queries scripts/calibration_data/text_queries.csv \
    --out scripts/calibration_data/text_labels.csv

python scripts/calibrate_thresholds.py prepare --mode image \
    --queries scripts/calibration_data/image_queries.csv \
    --out scripts/calibration_data/image_labels.csv
```

This runs each query through the real search path (same `search_hybrid` /
`search_vector` calls the app makes - the RRF ordering query itself isn't
touched) and writes the top-10 candidates per query to the `--out` CSV, with
an empty `label` column.

### 3. Label

Open the CSV and fill in `label` for each row (same rubric as below).

## Label rubric

| label | meaning |
|---|---|
| 0 | unrelated |
| 1 | loosely relevant |
| 2 | strongly relevant |

**Text mode** - judge against the query's intent:
- 2: the result is what someone searching that query is looking for (right
  template for a literal query; right vibe/sentiment for an abstract one).
- 1: in the right neighborhood (same general topic or tone) but not quite it.
- 0: unrelated.

**Image mode** - relevance is defined as **same template/format**, regardless
of caption:
- 2: same template as the query image (a different caption on the same
  format still counts), or an actual near-duplicate/reupload.
- 1: same general topic/subject but a different template.
- 0: unrelated.

It's fine to leave a row unlabeled if you're unsure - `calibrate` skips rows
with no label, it doesn't treat them as 0. You don't have to label every row
in the top-10; labeling the first 3-5 per query and leaving clear
non-matches at rank 8-10 blank (or quickly marking them 0) is enough to get
a usable distribution.

### Why meme_id, not a file, for image queries

`calibrate` re-runs every query fresh rather than trusting the cosine
recorded during labeling (the model/corpus can change between the two
steps). A meme_id can always be re-resolved to the same image bytes via
Cosmos + Blob storage, no matter which machine or session runs `calibrate`
later. A raw upload or a local file path can't - so image-mode queries are
always a corpus meme_id, both in the app page and the CLI script.

## Calibrate

```
python scripts/calibrate_thresholds.py calibrate --mode text \
    --labels scripts/calibration_data/text_labels.csv

python scripts/calibrate_thresholds.py calibrate --mode image \
    --labels scripts/calibration_data/image_labels.csv
```

`--queries` is optional here - the labels CSV already carries the query
text/meme_id for each row (both the page's export and `prepare`'s output
include it), so `calibrate` derives the query set from `--labels` directly.
Pass `--queries` explicitly only if you have a `--labels` file that doesn't
carry the `query` column for some reason.

This prints cosine distribution stats per label, suggested `mid`/`high`
(and `dup` for image) thresholds, and - if `matplotlib` is installed - writes
a histogram PNG to `scripts/calibration_data/`. Add `--logistic` to also fit
an optional (cosine, coverage, query length) logistic-regression fallback,
useful if the distributions overlap too much for a single cosine cutoff to
separate cleanly.

## Commit the thresholds

Add an entry to `TEXT_THRESHOLDS` / `IMAGE_THRESHOLDS` in
`memedb/relevance.py`, keyed by the `AZURE_VISION_MODEL_VERSION` you
calibrated against:

```python
TEXT_THRESHOLDS: dict[str, TextThresholds] = {
    "2024-02-01": TextThresholds(mid=0.31, high=0.37),
}
IMAGE_THRESHOLDS: dict[str, ImageThresholds] = {
    "2024-02-01": ImageThresholds(mid=0.58, high=0.77, dup=0.93),
}
```

Add a new entry rather than overwriting an old one when the vision model
version changes - the embedding space (and so the cosine ranges) shifts with
it, and keeping old entries around means historical runs stay interpretable.
