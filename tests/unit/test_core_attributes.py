"""Unit tests for tkcurses._core.attributes module."""

import pytest

from tkcurses._core.attributes import (
    A_NORMAL,
    A_STANDOUT,
    A_UNDERLINE,
    A_REVERSE,
    A_BLINK,
    A_DIM,
    A_BOLD,
    A_PROTECT,
    A_INVIS,
    A_ALTCHARSET,
    A_ITALIC,
    combine_attrs,
    has_attr,
    add_attr,
    remove_attr,
    attrs_to_str,
    style_to_attr,
)


class TestAttributeConstants:
    """Tests for attribute constants."""

    def test_a_normal_is_zero(self):
        """A_NORMAL should be zero."""
        assert A_NORMAL == 0

    def test_attributes_are_distinct(self):
        """Non-normal attributes should be distinct."""
        attrs = [A_STANDOUT, A_UNDERLINE, A_REVERSE, A_BLINK,
                 A_DIM, A_BOLD, A_PROTECT, A_INVIS, A_ALTCHARSET]
        # Filter out any that might be zero (platform-dependent)
        non_zero = [a for a in attrs if a != 0]
        assert len(set(non_zero)) == len(non_zero)

    def test_a_italic_exists(self):
        """A_ITALIC should exist (may be 0 on some platforms)."""
        assert isinstance(A_ITALIC, int)


class TestCombineAttrs:
    """Tests for combine_attrs function."""

    def test_combine_none(self):
        """Combining no attributes should return A_NORMAL."""
        assert combine_attrs() == A_NORMAL

    def test_combine_single(self):
        """Combining single attribute should return it."""
        assert combine_attrs(A_BOLD) == A_BOLD

    def test_combine_multiple(self):
        """Combining multiple attributes should OR them."""
        combined = combine_attrs(A_BOLD, A_UNDERLINE)
        assert combined & A_BOLD
        assert combined & A_UNDERLINE

    def test_combine_with_normal(self):
        """Combining with A_NORMAL should have no effect."""
        result = combine_attrs(A_BOLD, A_NORMAL)
        assert result == A_BOLD


class TestHasAttr:
    """Tests for has_attr function."""

    def test_has_single_attr(self):
        """has_attr should detect single attribute."""
        assert has_attr(A_BOLD, A_BOLD)
        assert has_attr(A_UNDERLINE, A_UNDERLINE)

    def test_has_attr_in_combination(self):
        """has_attr should detect attribute in combination."""
        combined = A_BOLD | A_UNDERLINE
        assert has_attr(combined, A_BOLD)
        assert has_attr(combined, A_UNDERLINE)
        assert not has_attr(combined, A_REVERSE)

    def test_has_normal(self):
        """has_attr with A_NORMAL always returns False since A_NORMAL is 0."""
        # A_NORMAL is 0, so (x & 0) != 0 is always False
        assert not has_attr(A_BOLD, A_NORMAL)
        assert not has_attr(0, A_NORMAL)

    def test_has_no_attr(self):
        """has_attr should return False when attribute not present."""
        assert not has_attr(A_BOLD, A_UNDERLINE)
        assert not has_attr(0, A_BOLD)


class TestAddAttr:
    """Tests for add_attr function."""

    def test_add_to_normal(self):
        """Adding to A_NORMAL should return the attribute."""
        result = add_attr(A_NORMAL, A_BOLD)
        assert result == A_BOLD

    def test_add_to_existing(self):
        """Adding to existing should combine."""
        result = add_attr(A_BOLD, A_UNDERLINE)
        assert has_attr(result, A_BOLD)
        assert has_attr(result, A_UNDERLINE)

    def test_add_already_present(self):
        """Adding already-present attribute should be idempotent."""
        result = add_attr(A_BOLD, A_BOLD)
        assert result == A_BOLD


class TestRemoveAttr:
    """Tests for remove_attr function."""

    def test_remove_present(self):
        """Removing present attribute should clear it."""
        combined = A_BOLD | A_UNDERLINE
        result = remove_attr(combined, A_BOLD)
        assert not has_attr(result, A_BOLD)
        assert has_attr(result, A_UNDERLINE)

    def test_remove_not_present(self):
        """Removing absent attribute should be no-op."""
        result = remove_attr(A_BOLD, A_UNDERLINE)
        assert result == A_BOLD

    def test_remove_all(self):
        """Removing last attribute should return A_NORMAL."""
        result = remove_attr(A_BOLD, A_BOLD)
        assert result == A_NORMAL


class TestAttrsToStr:
    """Tests for attrs_to_str function."""

    def test_normal(self):
        """A_NORMAL should produce 'A_NORMAL'."""
        assert attrs_to_str(A_NORMAL) == 'A_NORMAL'

    def test_single_attr(self):
        """Single attribute should produce its name."""
        result = attrs_to_str(A_BOLD)
        assert 'A_BOLD' in result

    def test_multiple_attrs(self):
        """Multiple attributes should all be listed."""
        combined = A_BOLD | A_UNDERLINE
        result = attrs_to_str(combined)
        assert 'A_BOLD' in result
        assert 'A_UNDERLINE' in result

    def test_format(self):
        """Result should be comma-separated."""
        combined = A_BOLD | A_UNDERLINE
        result = attrs_to_str(combined)
        # Should contain a comma if multiple
        assert ', ' in result


class TestStyleToAttr:
    """Tests for style_to_attr function."""

    def test_bold(self):
        """'bold' should map to A_BOLD."""
        assert style_to_attr('bold') == A_BOLD

    def test_underline(self):
        """'underline' should map to A_UNDERLINE."""
        assert style_to_attr('underline') == A_UNDERLINE

    def test_reverse(self):
        """'reverse' should map to A_REVERSE."""
        assert style_to_attr('reverse') == A_REVERSE

    def test_dim(self):
        """'dim' should map to A_DIM."""
        assert style_to_attr('dim') == A_DIM

    def test_standout(self):
        """'standout' should map to A_STANDOUT."""
        assert style_to_attr('standout') == A_STANDOUT

    def test_italic(self):
        """'italic' should map to A_ITALIC."""
        result = style_to_attr('italic')
        assert result == A_ITALIC

    def test_normal(self):
        """'normal' should map to A_NORMAL."""
        assert style_to_attr('normal') == A_NORMAL

    def test_case_insensitive(self):
        """Style names should be case-insensitive."""
        assert style_to_attr('BOLD') == A_BOLD
        assert style_to_attr('Bold') == A_BOLD
        assert style_to_attr('bOlD') == A_BOLD

    def test_unknown_returns_normal(self):
        """Unknown style should return A_NORMAL."""
        assert style_to_attr('unknown') == A_NORMAL
        assert style_to_attr('') == A_NORMAL
