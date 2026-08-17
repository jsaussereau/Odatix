# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
Derived metrics (odatix.lib.derived_metrics,
odatix.components.export_derived_metrics) and invariant parameter domains
(odatix.lib.param_domain).

A derived metric is a metric a record does not hold itself but gets from another
record; it is what links simulation results to synthesis results. These tests
cover the join rule (which dimensions two records must agree on, and how "match"
refines that), the "for" scope, the operation metrics, the whole-result-set pass
that writes the files back, and the invariant domains that let a single
simulation run stand for every value of a parameter domain.
"""

import os

import pytest

import odatix.lib.results_schema as results_schema
import odatix.lib.derived_metrics as derived_metrics
import odatix.lib.param_domain as param_domain
from odatix.components.export_derived_metrics import apply_derived_metrics


######################################
# Helpers
######################################

def synthesis_record(architecture="AsteRISC", configuration="rv32i", metrics=None, **domains):
  """A synthesis record: the base configuration lives under "main", like the exporter writes it."""
  full = configuration + "".join("+" + domain + "_" + value for domain, value in sorted(domains.items()))
  meta = {
    results_schema.META_TYPE: results_schema.TYPE_FMAX,
    results_schema.META_TOOL: "vivado",
    results_schema.META_TARGET: "xc7a100t",
    results_schema.META_ARCHITECTURE: architecture,
    results_schema.META_CONFIGURATION: full,
    results_schema.MAIN_DOMAIN_META_KEY: configuration,
  }
  meta.update(domains)
  return results_schema.make_record(meta, dict(metrics or {}))


def simulation_record(
  simulation="TB", architecture="AsteRISC", configuration="rv32i",
  metrics=None, invariant_domains=None, **domains
):
  arch_full = configuration + "".join("+" + domain + "/" + value for domain, value in sorted(domains.items()))
  return results_schema.make_simulation_record(
    simulation=simulation,
    architecture=architecture,
    configuration=configuration,
    arch_full=arch_full,
    run_dir=None,
    simulation_definition_dir=None,
    metrics=dict(metrics or {}),
    invariant_domains=invariant_domains,
  )


def config_from(definitions, groups=None):
  resolver = derived_metrics.GroupResolver(groups)
  metrics = [derived_metrics.DerivedMetric(name, d, resolver, "test") for name, d in definitions.items()]
  assert all(metric.valid for metric in metrics)
  return derived_metrics.DerivedMetricsConfig(path="test", metrics=metrics, resolver=resolver)


def metrics_of(record):
  return record["metrics"]


######################################
# Group resolution
######################################

class TestGroups:
  def test_a_group_expands_into_its_patterns(self):
    resolver = derived_metrics.GroupResolver({"cpus": ["AsteRISC/*", "Ibex/*"]})
    assert resolver.resolve("@cpus") == ["AsteRISC/*", "Ibex/*"]

  def test_groups_and_plain_patterns_mix_in_one_list(self):
    resolver = derived_metrics.GroupResolver({"cpus": ["AsteRISC/*"]})
    assert resolver.resolve(["@cpus", "Counter/*"]) == ["AsteRISC/*", "Counter/*"]

  def test_a_group_may_reference_another_one(self):
    resolver = derived_metrics.GroupResolver({"all": ["@cpus", "Counter/*"], "cpus": ["AsteRISC/*"]})
    assert resolver.resolve("@all") == ["AsteRISC/*", "Counter/*"]

  def test_a_circular_reference_resolves_instead_of_recursing(self):
    resolver = derived_metrics.GroupResolver({"a": ["@b"], "b": ["@a", "X/*"]})
    assert resolver.resolve("@a") == ["X/*"]

  def test_an_unknown_group_resolves_to_nothing(self):
    resolver = derived_metrics.GroupResolver({})
    assert resolver.resolve("@nope") == []

  def test_a_group_is_not_tied_to_architectures(self):
    """The same mechanism names sets of simulations, workflows or targets."""
    resolver = derived_metrics.GroupResolver({"benchmarks": ["TB_Dhrystone", "TB_Coremark"]})
    patterns = resolver.resolve("@benchmarks")
    assert derived_metrics.matches_any("TB_Coremark", patterns)
    assert not derived_metrics.matches_any("TB_Other", patterns)


######################################
# Record dimensions
######################################

class TestDimensions:
  def test_synthesis_and_simulation_agree_on_the_configuration_dimension(self):
    """One carries "main" and a decorated configuration, the other a plain one."""
    synth = derived_metrics.join_dimensions(synthesis_record(configuration="rv32i", MEM="1024I")["meta"])
    sim = derived_metrics.join_dimensions(simulation_record(configuration="rv32i", MEM="1024I")["meta"])
    assert synth[results_schema.META_CONFIGURATION] == "rv32i"
    assert sim[results_schema.META_CONFIGURATION] == "rv32i"
    assert synth["MEM"] == sim["MEM"] == "1024I"

  def test_how_a_job_ran_is_not_a_dimension(self):
    dimensions = derived_metrics.join_dimensions(synthesis_record()["meta"])
    for key in (results_schema.META_TOOL, results_schema.META_TYPE, results_schema.META_TIMESTAMP):
      assert key not in dimensions

  def test_informational_keys_are_not_dimensions(self):
    record = simulation_record()
    assert "_arch_full" in record["meta"]
    assert "_arch_full" not in derived_metrics.join_dimensions(record["meta"])

  def test_a_record_is_named_by_every_instance_it_belongs_to(self):
    names = derived_metrics.instance_names(simulation_record(simulation="TB_Dhrystone")["meta"])
    assert "AsteRISC" in names
    assert "AsteRISC/rv32i" in names
    assert "TB_Dhrystone" in names


######################################
# Matching
######################################

class TestMatching:
  def test_a_metric_is_imported_from_the_matching_record(self):
    records = [
      synthesis_record(configuration="rv32i"),
      simulation_record(configuration="rv32i", metrics={"Cycles": 1000}),
    ]
    derived_metrics.apply_derived_metrics(config_from({"Cycles": {"from": "simulation"}}), records)
    assert metrics_of(records[0]) == {"Cycles": 1000}

  def test_a_record_of_another_configuration_is_not_a_match(self):
    records = [
      synthesis_record(configuration="rv32im"),
      simulation_record(configuration="rv32i", metrics={"Cycles": 1000}),
    ]
    derived_metrics.apply_derived_metrics(config_from({"Cycles": {"from": "simulation", "optional": True}}), records)
    assert metrics_of(records[0]) == {}

  def test_a_domain_only_the_target_carries_does_not_constrain_the_match(self):
    """This is what makes an invariant domain broadcast with nothing to declare."""
    records = [
      synthesis_record(MEM="1024I"),
      synthesis_record(MEM="4096I"),
      simulation_record(metrics={"Cycles": 1000}),  # no MEM dimension at all
    ]
    derived_metrics.apply_derived_metrics(config_from({"Cycles": {"from": "simulation"}}), records)
    assert metrics_of(records[0])["Cycles"] == 1000
    assert metrics_of(records[1])["Cycles"] == 1000

  def test_a_shared_domain_does_constrain_the_match(self):
    records = [
      synthesis_record(MEM="1024I"),
      synthesis_record(MEM="4096I"),
      simulation_record(MEM="1024I", metrics={"Cycles": 1000}),
      simulation_record(MEM="4096I", metrics={"Cycles": 2000}),
    ]
    derived_metrics.apply_derived_metrics(config_from({"Cycles": {"from": "simulation"}}), records)
    assert metrics_of(records[0])["Cycles"] == 1000
    assert metrics_of(records[1])["Cycles"] == 2000

  def test_pin_reads_one_value_of_a_domain_whatever_the_target_holds(self):
    records = [
      synthesis_record(MEM="1024I"),
      synthesis_record(MEM="4096I"),
      simulation_record(MEM="1024I", metrics={"Cycles": 1000}),
      simulation_record(MEM="4096I", metrics={"Cycles": 2000}),
    ]
    definition = {"from": "simulation", "match": {"pin": {"MEM": "1024I"}}}
    derived_metrics.apply_derived_metrics(config_from({"Cycles": definition}), records)
    assert metrics_of(records[0])["Cycles"] == 1000
    assert metrics_of(records[1])["Cycles"] == 1000

  def test_ignore_drops_a_domain_from_the_join(self):
    records = [
      synthesis_record(MEM="1024I"),
      simulation_record(MEM="4096I", metrics={"Cycles": 1000}),
    ]
    definition = {"from": "simulation", "match": {"ignore": ["MEM"]}}
    derived_metrics.apply_derived_metrics(config_from({"Cycles": definition}), records)
    assert metrics_of(records[0])["Cycles"] == 1000

  def test_map_joins_domains_named_differently_on_each_side(self):
    records = [
      synthesis_record(Cache="1024I"),
      simulation_record(MEM="1024I", metrics={"Cycles": 1000}),
      simulation_record(MEM="4096I", metrics={"Cycles": 2000}),
    ]
    definition = {"from": "simulation", "match": {"map": {"MEM": "Cache"}}}
    derived_metrics.apply_derived_metrics(config_from({"Cycles": definition}), records)
    assert metrics_of(records[0])["Cycles"] == 1000

  def test_keys_joins_on_exactly_the_given_dimensions(self):
    records = [
      synthesis_record(configuration="rv32i", MEM="1024I"),
      simulation_record(configuration="rv32im", MEM="4096I", metrics={"Cycles": 1000}),
    ]
    definition = {"from": "simulation", "match": {"keys": [results_schema.META_ARCHITECTURE]}}
    derived_metrics.apply_derived_metrics(config_from({"Cycles": definition}), records)
    assert metrics_of(records[0])["Cycles"] == 1000

  def test_a_bare_on_key_still_works_although_yaml_reads_it_as_a_boolean(self):
    definition = {"from": "simulation", "match": {True: [results_schema.META_ARCHITECTURE]}}
    metric = derived_metrics.DerivedMetric("Cycles", definition, derived_metrics.GroupResolver(), "test")
    assert metric.match_on == [results_schema.META_ARCHITECTURE]

  def test_source_where_restricts_which_records_are_read(self):
    records = [
      synthesis_record(),
      simulation_record(simulation="TB_Other", metrics={"Cycles": 9}),
      simulation_record(simulation="TB_Dhrystone", metrics={"Cycles": 1000}),
    ]
    definition = {"from": "simulation", "source_where": {"simulation": "TB_Dhrystone"}}
    derived_metrics.apply_derived_metrics(config_from({"Cycles": definition}), records)
    assert metrics_of(records[0])["Cycles"] == 1000


######################################
# Ambiguity
######################################

class TestOnMultiple:
  @staticmethod
  def records():
    return [
      synthesis_record(),
      simulation_record(simulation="A", metrics={"Cycles": 1000}),
      simulation_record(simulation="B", metrics={"Cycles": 3000}),
    ]

  def test_several_matches_are_an_error_by_default(self):
    records = self.records()
    derived_metrics.apply_derived_metrics(config_from({"Cycles": {"from": "simulation"}}), records)
    assert metrics_of(records[0]) == {}

  @pytest.mark.parametrize(
    "how, expected",
    [("first", 1000), ("last", 3000), ("mean", 2000), ("min", 1000), ("max", 3000), ("sum", 4000)],
  )
  def test_an_explicit_rule_resolves_the_ambiguity(self, how, expected):
    records = self.records()
    definition = {"from": "simulation", "on_multiple": how}
    derived_metrics.apply_derived_metrics(config_from({"Cycles": definition}), records)
    assert metrics_of(records[0])["Cycles"] == expected


######################################
# Scope
######################################

class TestScope:
  def test_for_restricts_which_records_get_the_metric(self):
    records = [
      synthesis_record(architecture="AsteRISC"),
      synthesis_record(architecture="Counter", configuration="08bits"),
      simulation_record(architecture="AsteRISC", metrics={"Cycles": 1000}),
      simulation_record(architecture="Counter", configuration="08bits", metrics={"Cycles": 5}),
    ]
    definition = {"from": "simulation", "for": "@cpus"}
    config = config_from({"Cycles": definition}, groups={"cpus": ["AsteRISC/*"]})
    derived_metrics.apply_derived_metrics(config, records)
    assert metrics_of(records[0])["Cycles"] == 1000
    assert metrics_of(records[1]) == {}

  def test_a_scope_may_name_one_configuration(self):
    records = [
      synthesis_record(configuration="rv32i"),
      synthesis_record(configuration="rv32im"),
      simulation_record(configuration="rv32i", metrics={"Cycles": 1}),
      simulation_record(configuration="rv32im", metrics={"Cycles": 2}),
    ]
    definition = {"from": "simulation", "for": "AsteRISC/rv32i"}
    derived_metrics.apply_derived_metrics(config_from({"Cycles": definition}), records)
    assert metrics_of(records[0])["Cycles"] == 1
    assert metrics_of(records[1]) == {}

  def test_no_scope_means_every_record(self):
    records = [
      synthesis_record(architecture="AsteRISC"),
      synthesis_record(architecture="Counter", configuration="08bits"),
      simulation_record(architecture="AsteRISC", metrics={"Cycles": 1000}),
      simulation_record(architecture="Counter", configuration="08bits", metrics={"Cycles": 5}),
    ]
    derived_metrics.apply_derived_metrics(config_from({"Cycles": {"from": "simulation"}}), records)
    assert metrics_of(records[0])["Cycles"] == 1000
    assert metrics_of(records[1])["Cycles"] == 5

  def test_where_filters_on_any_meta_key(self):
    records = [
      synthesis_record(),
      simulation_record(metrics={"Cycles": 1000}),
    ]
    records[0]["meta"][results_schema.META_TARGET] = "other_target"
    definition = {"from": "simulation", "where": {"target": "xc7a*"}}
    derived_metrics.apply_derived_metrics(config_from({"Cycles": definition}), records)
    assert metrics_of(records[0]) == {}

  def test_apply_to_selects_which_kinds_of_record_get_the_metric(self):
    records = [
      synthesis_record(),
      simulation_record(metrics={"Cycles": 1000, "Fmax": None}),
    ]
    records[1]["metrics"].pop("Fmax")
    records[0]["metrics"]["Fmax"] = 100
    definition = {"from": "fmax_synthesis", "metric": "Fmax", "apply_to": "simulation"}
    derived_metrics.apply_derived_metrics(config_from({"Fmax": definition}), records)
    assert metrics_of(records[1])["Fmax"] == 100


######################################
# Operations
######################################

class TestOperations:
  def test_an_operation_may_use_an_imported_metric(self):
    records = [
      synthesis_record(metrics={"Frequency": 100}),
      simulation_record(metrics={"Cycles": 1000}),
    ]
    definitions = {
      "Cycles": {"from": "simulation"},
      "Runtime": {"type": "operation", "op": "Cycles / Frequency", "unit": "us"},
    }
    units = {}
    derived_metrics.apply_derived_metrics(config_from(definitions), records, units)
    assert metrics_of(records[0])["Runtime"] == 10
    assert units["Runtime"] == "us"

  def test_an_operation_missing_an_operand_writes_nothing(self):
    records = [synthesis_record(metrics={"Frequency": 100})]
    definitions = {"Runtime": {"type": "operation", "op": "Cycles / Frequency"}}
    derived_metrics.apply_derived_metrics(config_from(definitions), records)
    assert "Runtime" not in metrics_of(records[0])

  def test_a_definition_with_an_op_and_no_type_is_an_operation(self):
    metric = derived_metrics.DerivedMetric(
      "Runtime", {"op": "1 + 1"}, derived_metrics.GroupResolver(), "test"
    )
    assert metric.valid and metric.kind == derived_metrics.KIND_OPERATION


######################################
# Recomputation
######################################

class TestRecomputation:
  def test_deriving_twice_changes_nothing(self):
    records = [synthesis_record(), simulation_record(metrics={"Cycles": 1000})]
    config = config_from({"Cycles": {"from": "simulation"}})
    derived_metrics.apply_derived_metrics(config, records)
    first = [dict(record["metrics"]) for record in records]
    derived_metrics.apply_derived_metrics(config, records)
    assert [dict(record["metrics"]) for record in records] == first

  def test_a_metric_whose_definition_is_gone_is_dropped(self):
    records = [synthesis_record(), simulation_record(metrics={"Cycles": 1000})]
    derived_metrics.apply_derived_metrics(config_from({"Cycles": {"from": "simulation"}}), records)
    assert "Cycles" in metrics_of(records[0])
    derived_metrics.apply_derived_metrics(config_from({}), records)
    assert "Cycles" not in metrics_of(records[0])

  def test_a_derived_metric_never_replaces_a_measured_one(self):
    records = [
      synthesis_record(metrics={"Cycles": 42}),
      simulation_record(metrics={"Cycles": 1000}),
    ]
    derived_metrics.apply_derived_metrics(config_from({"Cycles": {"from": "simulation"}}), records)
    assert metrics_of(records[0])["Cycles"] == 42

  def test_overwrite_lets_it_replace_one(self):
    records = [
      synthesis_record(metrics={"Cycles": 42}),
      simulation_record(metrics={"Cycles": 1000}),
    ]
    definition = {"from": "simulation", "overwrite": True}
    derived_metrics.apply_derived_metrics(config_from({"Cycles": definition}), records)
    assert metrics_of(records[0])["Cycles"] == 1000


######################################
# Whole result set pass
######################################

class TestExport:
  @staticmethod
  def write_workspace(tmp_path, definitions_yaml):
    results = tmp_path / "results"
    results.mkdir()
    results_schema.dump_results_file(
      str(results / "results_vivado.yml"),
      {"Fmax": "MHz"},
      [synthesis_record(MEM="1024I", metrics={"Frequency": 100}),
       synthesis_record(MEM="4096I", metrics={"Frequency": 100})],
    )
    results_schema.dump_results_file(
      str(results / "results_simulation.yml"),
      {},
      [simulation_record(metrics={"Cycles": 1000}, invariant_domains=["MEM"])],
    )
    definitions = tmp_path / "derived_metrics.yml"
    definitions.write_text(definitions_yaml)
    return str(results), str(definitions)

  def test_a_metric_crosses_result_files(self, tmp_path):
    results, definitions = self.write_workspace(
      tmp_path, "derived_metrics:\n  Cycles:\n    from: simulation\n"
    )
    assert apply_derived_metrics(results, definitions)

    written = results_schema.load_results_file(os.path.join(results, "results_vivado.yml"))
    assert [record["metrics"]["Cycles"] for record in written.records] == [1000, 1000]

  def test_the_unit_of_a_derived_metric_is_recorded(self, tmp_path):
    results, definitions = self.write_workspace(
      tmp_path,
      "derived_metrics:\n"
      "  Cycles:\n    from: simulation\n"
      "  Runtime:\n    type: operation\n    op: Cycles / Frequency\n    unit: us\n",
    )
    apply_derived_metrics(results, definitions)

    written = results_schema.load_results_file(os.path.join(results, "results_vivado.yml"))
    assert written.units["Runtime"] == "us"
    assert written.units["Fmax"] == "MHz"  # the units already there are kept

  def test_a_removed_definition_takes_its_unit_with_it(self, tmp_path):
    results, definitions = self.write_workspace(
      tmp_path,
      "derived_metrics:\n  Cycles:\n    from: simulation\n    unit: cycles\n",
    )
    apply_derived_metrics(results, definitions)
    assert results_schema.load_results_file(os.path.join(results, "results_vivado.yml")).units["Cycles"] == "cycles"

    with open(definitions, "w") as f:
      f.write("derived_metrics: {}\n")
    apply_derived_metrics(results, definitions)

    written = results_schema.load_results_file(os.path.join(results, "results_vivado.yml"))
    assert "Cycles" not in written.units
    assert all("Cycles" not in record["metrics"] for record in written.records)

  def test_a_workspace_with_no_definition_file_is_not_an_error(self, tmp_path):
    results, _ = self.write_workspace(tmp_path, "derived_metrics: {}\n")
    assert apply_derived_metrics(results, str(tmp_path / "does_not_exist.yml"))

  def test_a_non_results_yaml_file_of_the_result_directory_is_skipped(self, tmp_path):
    results, definitions = self.write_workspace(
      tmp_path, "derived_metrics:\n  Cycles:\n    from: simulation\n"
    )
    with open(os.path.join(results, "notes.yml"), "w") as f:
      f.write("something: else\n")

    assert apply_derived_metrics(results, definitions)
    with open(os.path.join(results, "notes.yml")) as f:
      assert f.read() == "something: else\n"


######################################
# Invariant parameter domains
######################################

class TestInvariantDomainsDeclaration:
  def test_a_list_declares_domains_with_no_chosen_value(self):
    assert param_domain.parse_invariant_domains(["MEM", "Voltage"]) == {"MEM": None, "Voltage": None}

  def test_a_mapping_chooses_the_value_to_run(self):
    assert param_domain.parse_invariant_domains({"MEM": "1024I"}) == {"MEM": "1024I"}

  def test_a_list_of_mappings_is_accepted_too(self):
    assert param_domain.parse_invariant_domains([{"MEM": "1024I"}, "Voltage"]) == {"MEM": "1024I", "Voltage": None}

  def test_nothing_declared_is_no_domain(self):
    assert param_domain.parse_invariant_domains(None) == {}


class TestConfigurationCollapse:
  configurations = [
    "rv32i+MEM/1024I+Mul/fast",
    "rv32i+MEM/4096I+Mul/fast",
    "rv32i+MEM/1024I+Mul/slow",
    "rv32i+MEM/4096I+Mul/slow",
  ]

  def test_one_configuration_is_kept_per_class(self):
    kept, dropped = param_domain.collapse_invariant_configurations(self.configurations, {"MEM": None})
    assert dropped == 2
    assert sorted(kept) == ["rv32i+MEM/1024I+Mul/fast", "rv32i+MEM/1024I+Mul/slow"]

  def test_the_chosen_value_is_the_one_kept(self):
    kept, dropped = param_domain.collapse_invariant_configurations(self.configurations, {"MEM": "4096I"})
    assert dropped == 2
    assert sorted(kept) == ["rv32i+MEM/4096I+Mul/fast", "rv32i+MEM/4096I+Mul/slow"]

  def test_a_domain_that_still_discriminates_is_not_collapsed(self):
    kept, dropped = param_domain.collapse_invariant_configurations(self.configurations, {"Nope": None})
    assert dropped == 0
    assert sorted(kept) == sorted(self.configurations)

  def test_a_chosen_value_that_was_not_requested_falls_back_to_another_one(self):
    kept, _ = param_domain.collapse_invariant_configurations(self.configurations, {"MEM": "8192I"})
    assert len(kept) == 2
    assert all("MEM/" in configuration for configuration in kept)

  def test_nothing_declared_keeps_every_configuration(self):
    kept, dropped = param_domain.collapse_invariant_configurations(self.configurations, {})
    assert dropped == 0 and kept == self.configurations

  def test_a_configuration_name_splits_into_its_domains(self):
    assert param_domain.split_configuration("rv32i+MEM/1024I") == ("rv32i", {"MEM": "1024I"})
    assert param_domain.split_configuration("rv32i") == ("rv32i", {})


class TestInvariantDomainsInRecords:
  def test_an_invariant_domain_is_not_a_dimension_of_the_record(self):
    record = simulation_record(MEM="1024I", Mul="fast", invariant_domains=["MEM"])
    assert "MEM" not in record["meta"]
    assert record["meta"]["Mul"] == "fast"

  def test_what_actually_ran_stays_traceable(self):
    record = simulation_record(MEM="1024I", invariant_domains=["MEM"])
    assert record["meta"]["_arch_full"] == "rv32i+MEM/1024I"
    assert record["meta"]["_invariant_domains"] == ["MEM"]

  def test_declaring_none_keeps_every_domain(self):
    record = simulation_record(MEM="1024I")
    assert record["meta"]["MEM"] == "1024I"
