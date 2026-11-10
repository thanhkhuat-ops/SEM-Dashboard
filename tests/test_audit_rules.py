import pytest

from app.audit import rules


def test_merge_precedence():
    eff = rules.merge({"bid_floor": 0.3, "min_clicks": 30}, {"bid_floor": 0.25})
    assert eff["bid_floor"] == {"value": 0.25, "source": "account"}
    assert eff["min_clicks"] == {"value": 30, "source": "global"}
    assert eff["acos_target"] == {"value": 0.30, "source": "default"}
    assert set(eff) == set(rules.BY_KEY)


def test_validate():
    assert rules.validate("bid_max_down", 0.15) == 0.15
    assert rules.validate("harvest_enabled", 0) == 0
    with pytest.raises(ValueError):
        rules.validate("harvest_enabled", 2)
    with pytest.raises(ValueError):
        rules.validate("min_clicks", 20.5)
    with pytest.raises(ValueError):
        rules.validate("bid_max_down", 0.95)
    with pytest.raises(ValueError):
        rules.validate("khong_co", 1)


def test_acos_target_priority():
    groups, portfolios = {"532": 0.25}, {"P1": 0.4}
    assert rules.acos_target(0.3, groups, portfolios, portfolio_id="P1", group_id=532) == 0.4
    assert rules.acos_target(0.3, groups, portfolios, portfolio_id="P2", group_id=532) == 0.25
    assert rules.acos_target(0.3, groups, portfolios, group_id=1) == 0.3


def test_defaults_are_valid():
    for p in rules.PARAMS:
        assert rules.validate(p.key, p.default) == p.default
