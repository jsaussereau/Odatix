import os

import pytest

from odatix.lib.utils import copytree, copytree_keeps

FILES = [
    "build.sbt", "README.txt", "src/main/top.scala", "src/main/params.scala", "src/test/tb.scala",
    "project/build.properties", "docs/notes.txt", "tmp/out.v", "rtl/top.v", "rtl/sub/alu.v",
]

LISTS = [
    (None, None),
    (["src", "project", "build.sbt"], None),
    (None, ["*.txt", "docs/", "tmp/"]),
    (["src/main"], ["*/params.scala"]),
    (["rtl/*.v"], None),
    (["*.scala"], ["src/test"]),
]


@pytest.mark.parametrize("whitelist,blacklist", LISTS)
def test_agrees_with_copytree(tmp_path, whitelist, blacklist):
    src, dst = tmp_path / "src_dir", tmp_path / "dst_dir"
    for rel in FILES:
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text("x")
    copytree(str(src), str(dst), whitelist=whitelist, blacklist=blacklist)
    for rel in FILES:
        copied = (dst / rel).is_file()
        assert copytree_keeps(str(src), rel, whitelist, blacklist) == copied, rel
