"""What "odatix clean" and "odatix replace" say, and when they fail."""

import argparse

from odatix.components import clean, replace_params
from odatix.lib.settings import OdatixSettings


def _clean_args(**values):
    defaults = dict(settings_file=None, force=False, verbose=False, quiet=False, config="odatix.yml")
    defaults.update(values)
    return argparse.Namespace(**defaults)


class _Settings(object):
    valid = True
    clean_settings_file = "clean_settings.yml"


class TestClean:
    def test_a_profile_named_on_purpose_must_exist(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(str(tmp_path))
        assert clean.main(_clean_args(settings_file="nope.yml"), settings=_Settings()) is False
        assert 'Settings file "nope.yml" does not exist' in capsys.readouterr().out

    def test_a_pattern_matching_nothing_is_a_note_in_verbose_mode(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(str(tmp_path))
        (tmp_path / "profile.yml").write_text("remove_list:\n  - ./nothing_here\n")
        assert clean.main(_clean_args(settings_file="profile.yml", verbose=True), settings=_Settings()) is True
        out = capsys.readouterr().out
        assert "warning" not in out
        assert 'note: Nothing matches' in out and 'nothing_here' in out

    def test_it_says_nothing_of_it_otherwise(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(str(tmp_path))
        (tmp_path / "profile.yml").write_text("remove_list:\n  - ./nothing_here\n")
        clean.main(_clean_args(settings_file="profile.yml"), settings=_Settings())
        assert "nothing_here" not in capsys.readouterr().out

    def test_the_help_of_yes_says_what_it_does(self):
        parser = argparse.ArgumentParser()
        clean.add_arguments(parser)
        assert "dangerous" in parser.format_help() and "do not ask" not in parser.format_help()


class TestSettingsMessages:
    def test_a_missing_settings_file_points_at_odatix_init(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(str(tmp_path))
        OdatixSettings("missing.yml")
        out = capsys.readouterr().out
        assert '"odatix init"' in out and "--init" not in out


class TestReplace:
    def test_the_failure_message_quotes_the_pattern(self, tmp_path, capsys):
        base = tmp_path / "input.v"
        base.write_text("nothing to see\n")
        replacement = tmp_path / "params.txt"
        replacement.write_text("x\n")
        found = replace_params.replace_params(
            base_text_file=str(base), replacement_text_file=str(replacement), output_file=str(tmp_path / "out.v"),
            start_delimiter="// <nomatch>", stop_delimiter="// </end>",
        )
        assert found is False
        out = capsys.readouterr().out
        assert 'Could not find pattern "' in out
        assert out.count('"') % 2 == 0
