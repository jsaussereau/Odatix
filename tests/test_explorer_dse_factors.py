"""Tests for the breakdown of an exploration by what its designs are made of."""

import odatix.explorer.core.dse_factors as dse_factors
from odatix.explorer.core.dse import Campaign


def _campaign(evaluations, objectives=None, constraints=None, front=None):
    data = {
        "architecture": "alu",
        "objectives": objectives or [{"metric": "area", "goal": "min"}],
        "evaluations": evaluations,
        "front": front or [],
    }
    if constraints:
        data["constraints"] = constraints
    return Campaign("demo", "demo.yml", data)


def _evaluation(area, parameters=None, source=None, **extra):
    record = {"configuration": "alu+" + str(area), "parameters": parameters or {},
              "metrics": {"area": area}}
    if source is not None:
        record["source"] = source
    record.update(extra)
    return record


######################################
# What a campaign varied
######################################

def test_a_factor_that_never_changed_is_not_one():
    campaign = _campaign([
        _evaluation(100, {"width": 8, "pipeline": 1}),
        _evaluation(200, {"width": 16, "pipeline": 1}),
    ])
    assert [factor.label for factor in dse_factors.factors(campaign)] == ["width"]


def test_domains_come_from_the_meta_of_the_result():
    campaign = _campaign([
        _evaluation(100, source={"architecture": "alu", "tool": "vivado", "Cache": "off"}),
        _evaluation(200, source={"architecture": "alu", "tool": "vivado", "Cache": "on"}),
    ])
    factors = dse_factors.factors(campaign)
    assert [(factor.label, factor.kind) for factor in factors] == [("Cache", dse_factors.DOMAIN)]


def test_domains_fall_back_to_the_configuration_name():
    """An archive written before the meta was kept still names its domains."""
    campaign = _campaign([
        {"configuration": "alu+Cache/off+Mul/on", "metrics": {"area": 100}},
        {"configuration": "alu+Cache/on+Mul/on", "metrics": {"area": 200}},
    ])
    assert [factor.label for factor in dse_factors.factors(campaign)] == ["Cache"]


def test_a_domain_that_is_also_a_parameter_is_not_listed_twice():
    campaign = _campaign([
        _evaluation(100, {"width": 8}, source={"width": "8"}),
        _evaluation(200, {"width": 16}, source={"width": "16"}),
    ])
    assert [factor.label for factor in dse_factors.factors(campaign)] == ["width"]


def test_a_padded_code_is_a_name_and_not_a_number():
    """Reading "0011" as eleven would sort designs along a scale that means nothing."""
    campaign = _campaign([
        _evaluation(100, {"encoding": "0011", "size": "16"}),
        _evaluation(200, {"encoding": "0101", "size": "32"}),
    ])
    numeric = dict((factor.label, factor.numeric) for factor in dse_factors.factors(campaign))
    assert numeric == {"encoding": False, "size": True}


######################################
# What moved a metric
######################################

def test_the_factor_that_decides_the_metric_ranks_first():
    evaluations = []
    for cache in ("off", "on"):
        for index, mul in enumerate(("off", "on")):
            # The cache doubles the area; the multiplier moves it by a hair.
            area = (1000 if cache == "on" else 500) + index
            evaluations.append(_evaluation(area, source={"Cache": cache, "Mul": mul}))
            evaluations.append(_evaluation(area + 2, source={"Cache": cache, "Mul": mul}))
    ranked = dse_factors.impacts(_campaign(evaluations), "area")
    assert [result["factor"].label for result in ranked] == ["Cache", "Mul"]
    assert ranked[0]["impact"] > 0.9
    assert ranked[0]["best"] == "off"


def test_a_factor_with_a_value_per_design_does_not_explain_everything():
    """
    The correction is what this is for: a parameter that names every design
    would otherwise account for the whole spread without saying anything.
    """
    evaluations = [
        _evaluation(area, {"serial": index})
        for index, area in enumerate([100, 900, 250, 700, 300, 800, 150, 950])
    ]
    result = dse_factors.impact_of(_campaign(evaluations), dse_factors.factors(_campaign(
        evaluations))[0], "area")
    assert result["impact"] == 0.0


def test_the_direction_of_a_numeric_factor_is_reported():
    evaluations = [_evaluation(width * 10, {"width": width}) for width in (4, 8, 16, 32)]
    result = dse_factors.impacts(_campaign(evaluations), "area")[0]
    assert round(result["direction"], 6) == 1.0


def test_a_factor_is_not_broken_down_by_itself():
    campaign = _campaign(
        [_evaluation(100, {}, frequency=50), _evaluation(200, {}, frequency=100)],
        objectives=[{"metric": "frequency", "goal": "max"}],
    )
    factor = dse_factors.factors(campaign)[0]
    assert factor.label == "frequency"
    assert dse_factors.is_the_metric(factor, "frequency")
    assert dse_factors.impact_of(campaign, factor, "frequency") is None


######################################
# Value by value
######################################

def test_levels_count_the_designs_that_failed():
    campaign = _campaign([
        _evaluation(100, {"width": 8}),
        {"configuration": "alu+broken", "parameters": {"width": 16}, "failed": True,
         "metrics": {}},
        _evaluation(300, {"width": 16}),
    ])
    factor = dse_factors.factors(campaign)[0]
    rows = dse_factors.levels_of(campaign, factor, "area")
    assert [(row["level"], row["designs"], row["failed"]) for row in rows] == [
        (8.0, 1, 0), (16.0, 2, 1),
    ]


def test_a_level_the_front_prefers_is_enriched():
    front = [_evaluation(100, {"width": 8}), _evaluation(110, {"width": 8})]
    evaluations = front + [
        _evaluation(500, {"width": 16}), _evaluation(600, {"width": 16}),
    ]
    campaign = _campaign(evaluations, front=front)
    factor = dse_factors.factors(campaign)[0]

    def key_of(record):
        return (str(record.get("configuration")), record.get("frequency"), record.get("batch"))

    rows = dse_factors.levels_of(
        campaign, factor, "area", front_keys=set(key_of(record) for record in front),
        key_of=key_of,
    )
    shares = dict((row["level"], row["enrichment"]) for row in rows)
    # Half the designs, all of the front.
    assert shares[8.0] == 2.0
    assert shares[16.0] == 0.0
