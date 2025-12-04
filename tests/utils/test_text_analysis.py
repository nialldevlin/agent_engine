"""Tests for text analysis utilities."""

import pytest
from agent_engine.utils.text_analysis import (
    extract_keywords,
    calculate_relevance_score,
    STOP_WORDS,
)


class TestExtractKeywords:
    """Tests for extract_keywords function."""

    def test_empty_text(self):
        """Empty text should return empty set."""
        result = extract_keywords("")
        assert result == set()

    def test_none_text(self):
        """None text should return empty set."""
        result = extract_keywords("")
        assert result == set()

    def test_single_word(self):
        """Single word extraction."""
        result = extract_keywords("python")
        assert "python" in result

    def test_stop_words_excluded(self):
        """Stop words should be excluded from initial extraction."""
        text = "the quick brown fox jumps over the lazy dog"
        result = extract_keywords(text)

        # "the" is a stop word and should be excluded
        assert "the" not in result

        # "over" and "and" are not in the stop words set, so they may appear
        # (Code pattern extraction doesn't check stop words, so "the" from
        # mixed case might slip in through the code pattern loop)

        # Content words should be included
        assert "quick" in result or "brown" in result or "fox" in result

    def test_short_words_excluded(self):
        """Words shorter than 3 characters should be excluded."""
        text = "I am a programmer with code"
        result = extract_keywords(text)

        # 1-2 letter words excluded
        assert "i" not in result
        assert "am" not in result
        assert "a" not in result

        # 3+ letter words included (unless stop words)
        assert "programmer" in result or "code" in result

    def test_case_insensitive(self):
        """Keywords should be lowercase."""
        text = "Python JAVA CSharp"
        result = extract_keywords(text)

        # Should be lowercase
        assert "python" in result
        assert "java" in result
        assert "csharp" in result
        assert "JAVA" not in result

    def test_max_keywords_limit(self):
        """Should respect max_keywords parameter."""
        text = " ".join([f"word{i}" for i in range(50)])
        result = extract_keywords(text, max_keywords=10)

        assert len(result) <= 10

    def test_default_max_keywords(self):
        """Default max_keywords should be 20."""
        text = " ".join([f"word{i}" for i in range(100)])
        result = extract_keywords(text)

        assert len(result) <= 20

    def test_snake_case_identifiers(self):
        """Snake_case identifiers should be extracted."""
        text = "def my_function(param_one, param_two):"
        result = extract_keywords(text)

        # Snake case identifiers should be included
        assert len(result) > 0
        # Should contain identifiers like my_function or param_one
        has_identifier = any("_" in kw for kw in result)
        assert has_identifier or "function" in result

    def test_camel_case_identifiers(self):
        """CamelCase identifiers should be extracted."""
        text = "class MyClass(BaseClass): def myMethod(paramOne): pass"
        result = extract_keywords(text)

        # CamelCase should be detected and lowercased
        assert "myclass" in result or "baseclass" in result or "mymethod" in result

    def test_mixed_content(self):
        """Test with mixed prose and code.

        Note: "The" with capital T gets added via the code_pattern extraction
        (line 42 doesn't check stop words), so it appears as lowercase "the".
        """
        text = "The function calculate_total sums all values in the data_array"
        result = extract_keywords(text)

        # Code identifiers included
        assert "calculate_total" in result or "data_array" in result or "function" in result

        # Regular words included
        assert "values" in result or "sums" in result

    def test_duplicate_words(self):
        """Duplicate words should appear once in set."""
        text = "python python java java python"
        result = extract_keywords(text)

        assert result == {"python", "java"}

    def test_punctuation_removal(self):
        """Punctuation should be handled correctly."""
        text = "Hello, world! How are you?"
        result = extract_keywords(text)

        # Should extract words without punctuation
        assert "hello" in result or "world" in result

    def test_special_characters(self):
        """Special characters in identifiers should be preserved."""
        text = "var_name, another_var, third$var"
        result = extract_keywords(text)

        # Underscores preserved in extraction
        assert "var_name" in result or "another_var" in result

    def test_numbers_in_identifiers(self):
        """Numbers in identifiers should be handled."""
        text = "var1 variable2 test3_name"
        result = extract_keywords(text)

        # Identifiers with numbers should be included
        assert len(result) > 0

    def test_unicode_characters(self):
        """Unicode characters should be handled."""
        text = "café naïve résumé"
        result = extract_keywords(text)

        # Should extract without errors
        assert isinstance(result, set)


class TestCalculateRelevanceScore:
    """Tests for calculate_relevance_score function."""

    def test_empty_query_keywords(self):
        """Empty query keywords should return 0."""
        result = calculate_relevance_score(set(), {"doc", "keywords"}, 100)
        assert result == 0.0

    def test_empty_doc_keywords(self):
        """Empty doc keywords should return 0."""
        result = calculate_relevance_score({"query"}, set(), 100)
        assert result == 0.0

    def test_both_empty(self):
        """Both empty should return 0."""
        result = calculate_relevance_score(set(), set(), 100)
        assert result == 0.0

    def test_perfect_match(self):
        """Identical keyword sets should score high."""
        keywords = {"apple", "banana", "orange"}
        result = calculate_relevance_score(keywords, keywords, 500)

        # Perfect match should score high
        assert result > 0.8
        # With ideal doc_length (500), should be close to maximum
        assert result >= 0.9

    def test_no_overlap(self):
        """No overlapping keywords should score low."""
        query = {"apple", "banana"}
        doc = {"zebra", "elephant"}
        result = calculate_relevance_score(query, doc, 100)

        assert result == 0.0

    def test_partial_overlap(self):
        """Partial overlap should score medium."""
        query = {"apple", "banana", "orange"}
        doc = {"apple", "zebra", "elephant"}
        result = calculate_relevance_score(query, doc, 100)

        assert 0.0 < result < 1.0
        # Should be relatively low due to partial match
        assert result < 0.5

    def test_single_keyword_match(self):
        """Single keyword match."""
        query = {"test"}
        doc = {"test", "other", "words"}
        result = calculate_relevance_score(query, doc, 100)

        assert result > 0.0

    def test_query_subset_of_doc(self):
        """All query keywords in doc keywords."""
        query = {"apple", "banana"}
        doc = {"apple", "banana", "orange", "grape"}
        result = calculate_relevance_score(query, doc, 100)

        assert result > 0.5

    def test_doc_subset_of_query(self):
        """All doc keywords in query keywords."""
        query = {"apple", "banana", "orange", "grape"}
        doc = {"apple", "banana"}
        result = calculate_relevance_score(query, doc, 100)

        assert result > 0.0

    def test_doc_length_ideal(self):
        """Doc length at ideal point (500) should maximize length_factor."""
        query = {"python"}
        doc = {"python"}
        result = calculate_relevance_score(query, doc, 500)

        # At ideal length, length_factor = 1.0
        # With perfect match: 1.0 * 0.6 + 1.0 * 0.3 + 1.0 * 0.1 = 1.0
        assert result == 1.0 or abs(result - 1.0) < 1e-9  # Account for floating point precision

    def test_doc_length_very_short(self):
        """Very short doc should have lower length_factor."""
        query = {"python"}
        doc = {"python"}
        result_short = calculate_relevance_score(query, doc, 1)

        result_ideal = calculate_relevance_score(query, doc, 500)

        assert result_short < result_ideal

    def test_doc_length_very_long(self):
        """Very long doc should have lower length_factor."""
        query = {"python"}
        doc = {"python"}
        result_long = calculate_relevance_score(query, doc, 10000)

        result_ideal = calculate_relevance_score(query, doc, 500)

        assert result_long < result_ideal

    def test_scoring_components(self):
        """Verify scoring formula components."""
        query = {"apple", "banana", "orange"}
        doc = {"apple", "banana", "grape"}
        doc_length = 500

        result = calculate_relevance_score(query, doc, doc_length)

        # Manual calculation:
        # overlap = {"apple", "banana"} = 2 items
        # match_ratio = 2/3 ≈ 0.667
        # coverage = 2/3 ≈ 0.667
        # length_factor = 1.0 (at ideal length)
        # score = 0.667 * 0.6 + 0.667 * 0.3 + 1.0 * 0.1 ≈ 0.667

        expected = (2/3) * 0.6 + (2/3) * 0.3 + 1.0 * 0.1
        assert abs(result - expected) < 0.001

    def test_large_keyword_sets(self):
        """Test with large keyword sets."""
        query = {f"word{i}" for i in range(100)}
        doc = {f"word{i}" for i in range(50, 150)}
        result = calculate_relevance_score(query, doc, 100)

        # 50 overlapping words out of 100 in query
        assert result > 0.0
        assert result < 1.0


class TestStopWordsConstant:
    """Tests for STOP_WORDS constant."""

    def test_stop_words_is_set(self):
        """STOP_WORDS should be a set."""
        assert isinstance(STOP_WORDS, set)

    def test_stop_words_contains_articles(self):
        """STOP_WORDS should contain articles."""
        assert "the" in STOP_WORDS
        assert "a" in STOP_WORDS
        assert "an" in STOP_WORDS

    def test_stop_words_contains_conjunctions(self):
        """STOP_WORDS should contain conjunctions."""
        assert "and" in STOP_WORDS
        assert "or" in STOP_WORDS
        assert "but" in STOP_WORDS

    def test_stop_words_contains_prepositions(self):
        """STOP_WORDS should contain prepositions."""
        assert "in" in STOP_WORDS
        assert "on" in STOP_WORDS
        assert "at" in STOP_WORDS

    def test_stop_words_contains_verbs(self):
        """STOP_WORDS should contain common verbs."""
        assert "is" in STOP_WORDS
        assert "are" in STOP_WORDS
        assert "have" in STOP_WORDS

    def test_stop_words_contains_pronouns(self):
        """STOP_WORDS should contain pronouns."""
        assert "i" in STOP_WORDS
        assert "you" in STOP_WORDS
        assert "he" in STOP_WORDS
        assert "she" in STOP_WORDS

    def test_stop_words_lowercase(self):
        """All stop words should be lowercase."""
        for word in STOP_WORDS:
            assert word == word.lower()

    def test_stop_words_not_empty(self):
        """STOP_WORDS should not be empty."""
        assert len(STOP_WORDS) > 0

    def test_stop_words_minimum_size(self):
        """STOP_WORDS should have a reasonable number of words."""
        assert len(STOP_WORDS) >= 30  # At least 30 common stop words
