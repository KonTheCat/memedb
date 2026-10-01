from memedb.relevance import (
    bucket_image_results,
    bucket_text_results,
    lexical_coverage,
    tokenize,
)


def test_tokenize_uses_word_boundaries_not_substrings():
    # "cat" must not match inside "category" - token-set matching, not `in` on strings.
    query_tokens = tokenize("cat")
    doc_tokens = tokenize("a category of things")
    coverage, matched = lexical_coverage(query_tokens, doc_tokens)
    assert coverage == 0.0
    assert matched == []


def test_lexical_coverage_full_match():
    coverage, matched = lexical_coverage(tokenize("dog meme"), tokenize("such wow very dog meme format"))
    assert coverage == 1.0
    assert matched == ["dog", "meme"]


def test_lexical_coverage_partial_match():
    coverage, matched = lexical_coverage(tokenize("dog meme"), tokenize("such wow very dog format"))
    assert coverage == 0.5
    assert matched == ["dog"]


def test_lexical_coverage_empty_query_is_zero():
    coverage, matched = lexical_coverage(set(), tokenize("anything"))
    assert coverage == 0.0
    assert matched == []


# Text bucket boundaries, using the provisional placeholder thresholds
# (mid=0.30, high=0.36) that apply when a model version has no calibrated
# entry - see relevance._PROVISIONAL_TEXT.


def test_text_bucket_strong_on_high_cosine_alone():
    buckets, no_strong = bucket_text_results([(0.40, 0.0)], "uncalibrated-model")
    assert buckets == ["strong"]
    assert no_strong is False


def test_text_bucket_strong_on_mid_cosine_with_coverage():
    buckets, no_strong = bucket_text_results([(0.31, 0.6)], "uncalibrated-model")
    assert buckets == ["strong"]


def test_text_bucket_possible_on_coverage_alone():
    buckets, no_strong = bucket_text_results([(0.0, 0.2)], "uncalibrated-model")
    assert buckets == ["possible"]
    assert no_strong is True


def test_text_bucket_possible_on_mid_cosine_without_coverage():
    buckets, _ = bucket_text_results([(0.32, 0.0)], "uncalibrated-model")
    assert buckets == ["possible"]


def test_text_bucket_weak_below_all_thresholds():
    buckets, no_strong = bucket_text_results([(0.1, 0.0)], "uncalibrated-model")
    assert buckets == ["weak"]
    assert no_strong is True


def test_text_bucket_is_capped_non_increasing_down_the_list():
    # A later, lower-ranked result scoring higher than an earlier one (can
    # happen since bucket and RRF rank are computed from different signals)
    # must still be capped at the previous result's bucket.
    buckets, _ = bucket_text_results([(0.20, 0.0), (0.99, 1.0)], "uncalibrated-model")
    assert buckets == ["weak", "weak"]


def test_text_no_strong_matches_true_only_when_none_reach_strong():
    buckets, no_strong = bucket_text_results([(0.32, 0.0), (0.10, 0.0)], "uncalibrated-model")
    assert buckets == ["possible", "weak"]
    assert no_strong is True


# Image bucket boundaries, using the provisional placeholders
# (mid=0.55, high=0.75, dup=0.92).


def test_image_bucket_near_duplicate():
    buckets, no_strong = bucket_image_results([0.95], "uncalibrated-model")
    assert buckets == ["near_duplicate"]
    assert no_strong is False


def test_image_bucket_similar():
    buckets, no_strong = bucket_image_results([0.80], "uncalibrated-model")
    assert buckets == ["similar"]
    assert no_strong is False


def test_image_bucket_loose():
    buckets, no_strong = bucket_image_results([0.60], "uncalibrated-model")
    assert buckets == ["loose"]
    assert no_strong is True


def test_image_bucket_weak():
    buckets, no_strong = bucket_image_results([0.10], "uncalibrated-model")
    assert buckets == ["weak"]
    assert no_strong is True


def test_image_bucket_capped_non_increasing():
    buckets, _ = bucket_image_results([0.60, 0.95], "uncalibrated-model")
    assert buckets == ["loose", "loose"]
