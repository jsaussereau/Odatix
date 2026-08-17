"""Tests for odatix.lib.get_from_dict (safe dictionary access)."""

import pytest

from odatix.lib.get_from_dict import (
    get_from_dict,
    Key,
    KeyNotInDictError,
    BadValueInDictError,
)


class TestPresentKey:
    def test_returns_value_and_success(self):
        value, ok = get_from_dict("a", {"a": 42}, silent=True)
        assert value == 42
        assert ok

    def test_type_check_passes(self):
        value, ok = get_from_dict("a", {"a": 42}, type=int, silent=True)
        assert value == 42
        assert ok

    def test_type_check_fails_returns_default(self):
        value, ok = get_from_dict("a", {"a": "not an int"}, type=int, default_value=7, silent=True)
        assert value == 7
        assert not ok

    def test_type_check_fails_raises_when_asked(self):
        with pytest.raises(BadValueInDictError):
            get_from_dict("a", {"a": "x"}, type=int, behavior=Key.MANTADORY_RAISE, silent=True)

    def test_bool_is_not_confused_with_none_type(self):
        value, ok = get_from_dict("a", {"a": False}, type=bool, silent=True)
        assert value is False
        assert ok


class TestMissingKey:
    def test_returns_default(self):
        value, ok = get_from_dict("missing", {}, default_value="d", silent=True)
        assert value == "d"
        assert not ok

    def test_default_none(self):
        value, ok = get_from_dict("missing", {}, silent=True)
        assert value is None
        assert not ok

    def test_mandatory_raise(self):
        with pytest.raises(KeyNotInDictError):
            get_from_dict("missing", {}, behavior=Key.MANTADORY_RAISE, silent=True)

    def test_optional_raise(self):
        with pytest.raises(KeyNotInDictError):
            get_from_dict("missing", {}, behavior=Key.OPTIONAL_RAISE, silent=True)

    def test_mandatory_no_raise(self):
        value, ok = get_from_dict("missing", {}, behavior=Key.MANTADORY, silent=True)
        assert value is None
        assert not ok


class TestBadParent:
    def test_parent_not_a_dict(self):
        value, ok = get_from_dict("a", ["not", "a", "dict"], default_value=1, silent=True)
        assert value == 1
        assert not ok

    def test_parent_none(self):
        value, ok = get_from_dict("a", None, silent=True)
        assert value is None
        assert not ok
