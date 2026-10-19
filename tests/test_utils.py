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
    (src / "a.txt").write_text("a", encoding="utf-8")
    (src / "b.log").write_text("b")
    (src / "sub" / "c.txt").write_text("c", encoding="utf-8")
    return src


class TestCopytree:
    def test_full_copy(self, source_tree, tmp_path):
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst))
        assert (dst / "a.txt").read_text(encoding="utf-8") == "a"
        assert (dst / "sub" / "c.txt").read_text(encoding="utf-8") == "c"

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

    def test_whitelisted_directory_copies_its_subtree(self, source_tree, tmp_path):
        (source_tree / "sub" / "deep").mkdir()
        (source_tree / "sub" / "deep" / "d.v").write_text("d", encoding="utf-8")
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst), whitelist=["sub", "b.log"])
        assert (dst / "sub" / "c.txt").exists()
        assert (dst / "sub" / "deep" / "d.v").exists()
        assert (dst / "b.log").exists()
        assert not (dst / "a.txt").exists()

    def test_whitelist_nested_path(self, source_tree, tmp_path):
        (source_tree / "sub" / "other.txt").write_text("o", encoding="utf-8")
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst), whitelist=["./sub/c.txt"])
        assert (dst / "sub" / "c.txt").exists()
        assert not (dst / "sub" / "other.txt").exists()
        assert not (dst / "a.txt").exists()

    def test_whitelist_prefix_is_not_a_directory_match(self, source_tree, tmp_path):
        (source_tree / "subx").mkdir()
        (source_tree / "subx" / "e.txt").write_text("e", encoding="utf-8")
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst), whitelist=["sub"])
        assert (dst / "sub" / "c.txt").exists()
        assert not (dst / "subx").exists()

    def test_destination_inside_source_is_not_copied(self, source_tree):
        dst = source_tree / "work"
        copytree(str(source_tree), str(dst))
        assert (dst / "sub" / "c.txt").exists()
        assert not (dst / "work").exists()

    def test_keeps_permission_bits_and_mtime(self, source_tree, tmp_path):
        script = source_tree / "run.sh"
        script.write_text("#!/bin/sh\n", encoding="utf-8")
        os.chmod(str(script), 0o750)
        os.utime(str(script), (1000000000, 1000000000))
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst))
        copied = os.stat(str(dst / "run.sh"))
        if os.name == "posix":
            # Windows only has a read-only bit
            assert copied.st_mode & 0o777 == 0o750
        assert int(copied.st_mtime) == 1000000000

    def test_slow_file_system_copies_in_parallel(self, source_tree, tmp_path, monkeypatch):
        import odatix.lib.utils as utils
        for i in range(40):
            (source_tree / "sub" / ("f%d.v" % i)).write_text(str(i), encoding="utf-8")
        # Every file looks slow: the probe switches to the thread pool
        monkeypatch.setattr(utils, "COPYTREE_SLOW_FILE_SECONDS", -1)
        monkeypatch.setattr(utils, "COPYTREE_PROBE_FILES", 2)
        dst = tmp_path / "dst"
        copytree(str(source_tree), str(dst), blacklist=["*.log"])
        for i in range(40):
            assert (dst / "sub" / ("f%d.v" % i)).read_text(encoding="utf-8") == str(i)
        assert (dst / "a.txt").exists()
        assert not (dst / "b.log").exists()

    def test_parallel_copy_error_is_raised(self, source_tree, tmp_path, monkeypatch):
        import odatix.lib.utils as utils
        for i in range(10):
            (source_tree / ("f%d.v" % i)).write_text(str(i), encoding="utf-8")
        try:
            os.symlink(str(source_tree / "missing"), str(source_tree / "zz_broken"))
        except OSError:
            pytest.skip("symbolic links need a privilege on Windows")
        monkeypatch.setattr(utils, "COPYTREE_SLOW_FILE_SECONDS", -1)
        monkeypatch.setattr(utils, "COPYTREE_PROBE_FILES", 1)
        with pytest.raises(OSError):
            copytree(str(source_tree), str(tmp_path / "dst"))


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
        (target / "leftover.txt").write_text("x", encoding="utf-8")
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


class TestServerPort:
    """GUI / Explorer port choice (odatix-gui -p, odatix-explorer -p)."""

    def _listen(self):
        import socket
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        return server

    def test_a_listening_port_is_skipped_without_p(self):
        server = self._listen()
        try:
            port = server.getsockname()[1]
            assert find_free_port("127.0.0.1", port) != port
        finally:
            server.close()

    def test_an_explicit_port_in_use_is_an_error_not_another_port(self):
        server = self._listen()
        try:
            with pytest.raises(SystemExit) as error:
                find_free_port("127.0.0.1", server.getsockname()[1], strict=True)
            assert error.value.code == 1
        finally:
            server.close()

    def test_an_explicit_free_port_is_kept(self):
        from odatix.lib.utils import port_is_free
        server = self._listen()
        port = server.getsockname()[1]
        server.close()
        assert port_is_free("127.0.0.1", port)
        assert find_free_port("127.0.0.1", port, strict=True) == port

    def test_time_wait_does_not_move_a_restarted_server(self):
        # A server stopped after serving a connection leaves it in TIME_WAIT on
        # its side (the side that closes first): the port must stay usable.
        import socket
        import time
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # as waitress does
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        client = socket.create_connection(("127.0.0.1", port))
        connection, _ = server.accept()
        connection.close()  # server side closes first: TIME_WAIT is on the server port
        client.recv(1)
        client.close()
        server.close()
        time.sleep(0.2)
        assert find_free_port("127.0.0.1", port, strict=True) == port


def test_a_closed_stdin_answers_no_instead_of_crashing(monkeypatch, capsys):
    import io
    from odatix.lib.utils import ask_yes_no

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert ask_yes_no() is False
    assert "-y/--noask" in capsys.readouterr().out
