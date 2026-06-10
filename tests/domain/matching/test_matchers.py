from emule_indexer.domain.matching.matchers import CoverageMatcher, KeywordMatcher, RegexMatcher
from emule_indexer.domain.matching.models import FileCandidate


def test_keyword_single_word_present() -> None:
    matcher = KeywordMatcher("keroro")
    assert matcher.matches(FileCandidate(filename="Keroro 062A.avi")) is True


def test_keyword_single_word_absent() -> None:
    matcher = KeywordMatcher("titar")
    assert matcher.matches(FileCandidate(filename="Keroro 062A.avi")) is False


def test_keyword_multiword_contiguous_present() -> None:
    matcher = KeywordMatcher("mission titar")
    candidate = FileCandidate(filename="Keroro Mission Titar 062A.avi")
    assert matcher.matches(candidate) is True


def test_keyword_multiword_non_contiguous_absent() -> None:
    matcher = KeywordMatcher("mission titar")
    candidate = FileCandidate(filename="mission keroro titar.avi")
    assert matcher.matches(candidate) is False


def test_keyword_accent_and_case_insensitive_via_tokenize() -> None:
    matcher = KeywordMatcher("teletoon")
    assert matcher.matches(FileCandidate(filename="Keroro TÉLÉTOON.avi")) is True


def test_keyword_empty_phrase_matches_anything() -> None:
    matcher = KeywordMatcher("")
    assert matcher.matches(FileCandidate(filename="whatever.avi")) is True


def test_keyword_phrase_longer_than_filename_is_absent() -> None:
    matcher = KeywordMatcher("keroro mission titar special")
    assert matcher.matches(FileCandidate(filename="keroro mission titar.avi")) is False


def test_regex_literal_matches_case_and_accent_insensitive() -> None:
    # Le pattern littéral "teletoon" matche "Télétoon" grâce à fold(raw).
    matcher = RegexMatcher("teletoon")
    assert matcher.matches(FileCandidate(filename="Keroro Télétoon.avi")) is True


def test_regex_segment_id_style_pattern() -> None:
    matcher = RegexMatcher(r"n[°o]?\s*0*62\s*a")
    assert matcher.matches(FileCandidate(filename="Keroro N°062A.avi")) is True


def test_regex_no_match_returns_false() -> None:
    matcher = RegexMatcher("teletoon")
    assert matcher.matches(FileCandidate(filename="autre fichier.mkv")) is False


def test_regex_uppercase_pattern_without_i_flag_does_not_match_folded_input() -> None:
    # fold() minusculise déjà ; un pattern en MAJUSCULES sans (?i) ne matche pas.
    matcher = RegexMatcher("TELETOON", flags="")
    assert matcher.matches(FileCandidate(filename="Keroro Télétoon.avi")) is False


def test_coverage_exact_title_is_one_and_matches() -> None:
    matcher = CoverageMatcher("Les demoiselles cambrioleuses", min=0.6)
    candidate = FileCandidate(filename="Keroro 062A Les demoiselles cambrioleuses.avi")
    assert matcher.value(candidate) == 1.0
    assert matcher.matches(candidate) is True


def test_coverage_one_typo_within_fuzz_still_matches() -> None:
    matcher = CoverageMatcher("Les demoiselles cambrioleuses", min=0.6)
    # "demoiseles" (un 'l' manquant) reste >= fuzz 0.85 vs "demoiselles".
    candidate = FileCandidate(filename="demoiseles cambrioleuses.avi")
    assert matcher.value(candidate) == 1.0
    assert matcher.matches(candidate) is True


def test_coverage_unrelated_is_zero_and_no_match() -> None:
    matcher = CoverageMatcher("Les demoiselles cambrioleuses", min=0.6)
    candidate = FileCandidate(filename="totalement autre chose.mkv")
    assert matcher.value(candidate) == 0.0
    assert matcher.matches(candidate) is False


def test_coverage_empty_reference_is_zero() -> None:
    # Référence faite uniquement de stopwords -> aucun token significatif -> 0.0.
    matcher = CoverageMatcher("les des un une", min=0.6)
    candidate = FileCandidate(filename="les demoiselles.avi")
    assert matcher.value(candidate) == 0.0
    assert matcher.matches(candidate) is False


def test_coverage_partial_fraction_at_min_boundary_matches() -> None:
    # 1 token significatif couvert sur 2 -> value 0.5 ; min=0.5 -> match (>= inclusif).
    matcher = CoverageMatcher("demoiselles cambrioleuses", min=0.5)
    candidate = FileCandidate(filename="demoiselles autre.avi")
    assert matcher.value(candidate) == 0.5
    assert matcher.matches(candidate) is True


def test_coverage_partial_fraction_below_min_does_not_match() -> None:
    # Même value 0.5 mais min=0.6 -> sous le seuil -> pas de match (value non nulle).
    matcher = CoverageMatcher("demoiselles cambrioleuses", min=0.6)
    candidate = FileCandidate(filename="demoiselles autre.avi")
    assert matcher.value(candidate) == 0.5
    assert matcher.matches(candidate) is False
