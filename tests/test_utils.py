"""Tests for odatix.lib.utils (file operations and misc helpers)."""

import os
import re

import pytest

from odatix.lib.utils import (
    copytree,
    chunk_list,
    read_from_list,
    KeyNotInListError,
    BadValueInListError,
    create_dir,
    merge_dicts_of_lists,
    get_timestamp_string,
    find_free_port,
    safe_df_append,
)


######################################
# copytree
######################################

@pytest.fixture
def source_tree(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_text("a")
    (src / "b.log").write_text("b")
    (src / "sub" / "c.txt").write_text("c")
    return src


class TestCopytree:
    def test_full_copy(self, source_tree, tmp_path):
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst))
        assert (dst / "a.txt").read_text() == "a"
        assert (dst / "sub" / "c.txt").read_text() == "c"

    def test_existing_destination_raises(self, source_tree, tmp_path):
        dst = tmp_path / "dst"
        dst.mkdir()
        with pytest.raises(FileExistsError):
            copytree(str(source_tree), str(dst))

    def test_dirs_exist_ok(self, source_tree, tmp_path):
        dst = tmp_path / "dst"
        dst.mkdir()
        copytree(str(source_tree), str(dst), dirs_exist_ok=True)
        assert (dst / "a.txt").exists()

    def test_blacklist(self, source_tree, tmp_path):
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst), blacklist=["*.log"])
        assert (dst / "a.txt").exists()
        assert not (dst / "b.log").exists()

    def test_whitelist(self, source_tree, tmp_path):
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst), whitelist=["*.txt"])
        assert (dst / "a.txt").exists()
        assert not (dst / "b.log").exists()

    def test_blacklisted_directory_is_not_explored(self, source_tree, tmp_path):
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst), blacklist=["sub"])
        assert not (dst / "sub").exists()


######################################
# Misc helpers
######################################

class TestChunkList:
    def test_even_chunks(self):
        assert list(chunk_list([1, 2, 3, 4], 2)) == [[1, 2], [3, 4]]

    def test_uneven_chunks(self):
        assert list(chunk_list([1, 2, 3], 2)) == [[1, 2], [3]]

    def test_empty(self):
        assert list(chunk_list([], 3)) == []


class TestReadFromList:
    def test_found(self):
        assert read_from_list("k", {"k": 1}, "f", script_name="t") == 1

    def test_type_ok(self):
        assert read_from_list("k", {"k": True}, "f", type=bool, print_error=False) is True

    def test_type_mismatch_raises(self):
        with pytest.raises(BadValueInListError):
            read_from_list("k", {"k": "str"}, "f", type=int, print_error=False)

    def test_missing_raises(self):
        with pytest.raises(KeyNotInListError):
            read_from_list("k", {}, "f", print_error=False)

    def test_missing_no_raise_returns_false(self):
        assert read_from_list("k", {}, "f", raise_if_missing=False, print_error=False) is False


class TestCreateDir:
    def test_creates_new(self, tmp_path):
        target = tmp_path / "newdir"
        create_dir(str(target))
        assert target.is_dir()

    def test_replaces_existing(self, tmp_path):
        target = tmp_path / "d"
        target.mkdir()
        (target / "leftover.txt").write_text("x")
        create_dir(str(target))
        assert target.is_dir()
        assert not (target / "leftover.txt").exists()


class TestMergeDictsOfLists:
    def test_disjoint_keys(self):
        assert merge_dicts_of_lists({"a": [1]}, {"b": [2]}) == {"a": [1], "b": [2]}

    def test_common_key_union_sorted(self):
        assert merge_dicts_of_lists({"a": [3, 1]}, {"a": [2, 3]}) == {"a": [1, 2, 3]}

    def test_empty_merging_dict(self):
        assert merge_dicts_of_lists({"a": [1]}, {}) == {"a": [1]}


class TestSmallHelpers:
    def test_timestamp_format(self):
        assert re.match(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$", get_timestamp_string())

    def test_find_free_port(self):
        port = find_free_port("127.0.0.1", 49500)
        assert 49500 <= port < 49600

    def test_safe_df_append(self):
        import pandas as pd

        df = pd.DataFrame(columns=["a"])
        df = safe_df_append(df, {"a": 1})
        assert len(df) == 1
        assert df.iloc[0]["a"] == 1
