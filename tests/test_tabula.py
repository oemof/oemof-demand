# -*- coding: utf-8 -*-

"""
Tests for the single zone building model.

SPDX-FileCopyrightText: Uwe Krien <uwe.krien@ifam.fraunhofer.de>
SPDX-License-Identifier: MIT
"""

import pandas as pd
import pytest

from oemof.demand.tabula import single_zone_building as szb


# ---------------------------------------------------------------------------
# check_type
# ---------------------------------------------------------------------------
class TestCheckType:
    def test_dataframe(self):
        df = pd.DataFrame({"a": [1]})
        assert isinstance(szb.check_type(df), pd.DataFrame)

    def test_float(self):
        assert szb.check_type(5.0) == 5.0

    def test_int_is_converted_to_float(self):
        assert isinstance(szb.check_type(5), float)
        assert szb.check_type(5) == 5.0

    def test_numeric_string_is_converted_to_float(self):
        assert szb.check_type("5.5") == 5.5

    def test_invalid_type_raises(self):
        # float(<list>) raises TypeError -> except -> not a float -> raise
        with pytest.raises(TypeError, match="not supported"):
            szb.check_type(["not", "supported"])

    def test_invalid_type_dict_raises(self):
        with pytest.raises(TypeError, match="not supported"):
            szb.check_type({"a": 1})


# ---------------------------------------------------------------------------
# heat_losses_transmission_component
# ---------------------------------------------------------------------------
def test_heat_losses_transmission_component_scalar():
    """Example from the docstring: Q = A * U * HDD * 24 * 0.001."""
    assert szb.heat_losses_transmission_component(10, 5, 200) == pytest.approx(
        240.0
    )


def test_heat_losses_transmission_component_correction_factor():
    result = szb.heat_losses_transmission_component(10, 5, 200, 0.5)
    assert result == pytest.approx(120.0)


def test_heat_losses_transmission_component_series():
    area = pd.Series([10, 20], index=[0, 1])
    u_value = pd.Series([5, 2], index=[0, 1])
    result = szb.heat_losses_transmission_component(area, u_value, 200)
    expected = area * u_value * 200 * 24 * 0.001
    pd.testing.assert_series_equal(result, expected)


# ---------------------------------------------------------------------------
# squeeze_to_series
# ---------------------------------------------------------------------------
def test_squeeze_to_series():
    df = pd.DataFrame({"a": [0.7]})
    szb.squeeze_to_series([df, 1.0])
    # squeezes in place; just ensure no error is raised on mixed inputs
    assert df.shape == (1, 1)


# ---------------------------------------------------------------------------
# EnvelopeParameter
# ---------------------------------------------------------------------------
class TestEnvelopeParameter:
    def setup_method(self):
        self.env = szb.EnvelopeParameter(wall=34, window=5, roof=20, floor=15)

    def test_parts(self):
        assert self.env.parts == ["wall", "window", "roof", "floor"]

    def test_default_correction_factors(self):
        assert self.env.correction_factors == {
            "wall": 1,
            "window": 1,
            "roof": 1,
            "floor": 1,
        }

    def test_explicit_correction_factors(self):
        # Non-None correction_factors path in __init__
        env = szb.EnvelopeParameter(
            wall=34,
            window=5,
            roof=20,
            floor=15,
            correction_factors={"wall": 2},
        )
        assert env.correction_factors == {"wall": 2}

    def test_df_multilevel_for_scalars(self):
        df = self.env.df
        assert df.shape == (1, 4)
        assert isinstance(df.columns, pd.MultiIndex)
        assert df.loc[0, ("wall", "wall")] == 34

    def test_flat_df(self):
        assert list(self.env.flat_df.columns) == [
            "wall",
            "window",
            "roof",
            "floor",
        ]
        assert self.env.flat_df.loc[0, "window"] == 5

    def test_df_concat_for_dataframe_parts(self):
        # Mixed -> concat branch of the df property
        wall = pd.DataFrame({"wall_1": [10, 12], "wall_2": [14, 16]})
        window = pd.DataFrame({"window_1": [4, 5]})
        env = szb.EnvelopeParameter(wall=wall, window=window)
        df = env.df
        assert isinstance(df.columns, pd.MultiIndex)
        assert df["wall"].shape == (2, 2)
        assert df["window"].shape == (2, 1)

    def test_flat_df_with_dataframe_parts(self):
        wall = pd.DataFrame({"wall_1": [10, 12]})
        env = szb.EnvelopeParameter(wall=wall)
        assert list(env.flat_df.columns) == ["wall_1"]

    def test_add_correction_factors(self):
        self.env.add_correction_factors({"wall": 0.5})
        assert self.env.correction_factors["wall"] == 0.5

    def test_add_correction_factors_with_missing(self):
        self.env.add_correction_factors({"wall": 0.5}, add_missing=True)
        assert self.env.correction_factors == {
            "wall": 0.5,
            "window": 1,
            "roof": 1,
            "floor": 1,
        }

    def test_add_correction_factors_unknown_part(self):
        with pytest.raises(ValueError, match="not found in column list"):
            self.env.add_correction_factors({"ceiling": 0.5})

    def test_uses_area_keys_from_config(self):
        # 'Tür' -> window, 'Boden' -> floor as defined in demand.ini
        df = pd.DataFrame(
            {"Wall": [10], "Tür": [3], "Dach": [20], "Boden": [15]}
        )
        env = szb.EnvelopeParameter.from_dataframe(df)
        assert float(env.window.iloc[0, 0]) == 3
        assert float(env.floor.iloc[0, 0]) == 15


# ---------------------------------------------------------------------------
# BuildingTable
# ---------------------------------------------------------------------------
class TestBuildingTable:
    def setup_method(self):
        self.env_area = szb.EnvelopeParameter(
            floor=15, window=5, roof=20, wall=34
        )
        self.bt = szb.BuildingTable(
            area=self.env_area,
            conditioned_floor_area=230,
            floor_height=2.5,
            window_orientation_factor=0.7,
        )
        self.env_u = szb.EnvelopeParameter(
            wall=0.5, roof=0.5, window=0.3, floor=0.3
        )

    def test_attributes(self):
        assert self.bt.floor_height == 2.5
        assert self.bt.conditioned_floor_area == 230
        assert self.bt.window_orientation_factor == 0.7

    def _params(self):
        return dict(
            u_value=self.env_u,
            thermal_bridges_factor=0.1,
            ventilation_rate=0.6,
            transmittance_windows=0.6,
            gain_utilisation_factor=0.958363,
            heating_degree_days=3497,
            heating_days=222,
            irradiation_heating_season=403,
        )

    def test_heat_losses_ventilation_building(self):
        # mass_flow = 230 * 2.5 * 0.6 * 1.2 = 414
        expected = (1.020 / 3600) * 414 * 24 * 3497
        result = self.bt.heat_losses_ventilation_building(0.6, 3497)
        assert result == pytest.approx(expected)

    def test_heat_losses_ventilation_recovery_and_custom(self):
        base = self.bt.heat_losses_ventilation_building(0.6, 100)
        with_recovery = self.bt.heat_losses_ventilation_building(
            0.6, 100, recovery_factor=0.5
        )
        assert with_recovery == pytest.approx(base * 0.5)
        # custom air properties fill the remaining kwargs
        custom = self.bt.heat_losses_ventilation_building(
            0.6, 100, rho_air=1.5, heat_capacity_air=2.0
        )
        assert custom > base

    def test_thermal_bridges(self):
        envelope_sum = self.env_area.df.sum(axis=1)
        result = self.bt.thermal_bridges(34, 0.1)
        expected = envelope_sum * 0.1 * 34
        pd.testing.assert_series_equal(result, expected)

    def test_heat_losses_building_columns(self):
        losses = self.bt.heat_losses_building(
            u_value=self.env_u.flat_df,
            heating_degree_days=3497,
            ventilation_rate=0.6,
            thermal_bridges_factor=0.1,
        )
        assert list(losses.columns) == [
            "wall",
            "window",
            "roof",
            "floor",
            "thermal bridges",
            "ventilation",
        ]

    def test_internal_heat_sources_series_input(self):
        area = pd.Series(data=[230], index=[0])
        height = pd.Series(data=[2.5], index=[0])
        orient = pd.Series(data=[0.7], index=[0])
        bt = szb.BuildingTable(
            area=pd.DataFrame({"window": [5]}, index=[0]),
            conditioned_floor_area=area,
            floor_height=height,
            window_orientation_factor=orient,
        )
        sg = bt.internal_heat_sources(222)
        assert isinstance(sg, pd.Series)
        assert sg.name == "internal heat sources"
        assert round(float(sg[0]), 2) == 3455.74

    def test_solar_gain_with_dataframe_window(self):
        env = szb.EnvelopeParameter(floor=2, window=5, roof=20, wall=4)
        bt = szb.BuildingTable(
            area=env,
            conditioned_floor_area=pd.Series(data=[230], index=[0]),
            floor_height=pd.Series(data=[2.5], index=[0]),
            window_orientation_factor=pd.Series(data=[0.7], index=[0]),
        )
        sg = bt.solar_gain(400, 0.6, 0.94)
        assert isinstance(sg, pd.Series)
        assert sg.name == "solar gain"
        assert round(float(sg[0]), 2) == 298.47

    def test_annual_heating_demand(self):
        result = self.bt.annual_heating_demand(**self._params())
        assert round(float(result.sum()), 3) == 9405.615

    def test_specific_annual_heating_demand(self):
        result = self.bt.specific_annual_heating_demand(**self._params())
        assert round(float(result.sum()), 3) == 40.894

    def test_annual_heating_demand_adjustment_factor(self):
        base = self.bt.annual_heating_demand(**self._params())
        doubled = self.bt.annual_heating_demand(
            **dict(self._params(), adjustment_factor=2)
        )
        pd.testing.assert_series_equal(doubled, base * 2)


# ---------------------------------------------------------------------------
# Regression / docstring examples as standalone numbers
# ---------------------------------------------------------------------------
def test_docstring_examples_are_reproducible():
    env_area = szb.EnvelopeParameter(floor=15, window=5, roof=20, wall=34)
    bt = szb.BuildingTable(
        area=env_area,
        conditioned_floor_area=230,
        floor_height=2.5,
        window_orientation_factor=0.7,
    )
    env_u = szb.EnvelopeParameter(wall=0.5, roof=0.5, window=0.3, floor=0.3)

    annual = bt.annual_heating_demand(
        u_value=env_u,
        heating_degree_days=3497,
        heating_days=222,
        thermal_bridges_factor=0.1,
        ventilation_rate=0.6,
        irradiation_heating_season=403,
        gain_utilisation_factor=0.958363,
        transmittance_windows=0.6,
    )
    specific = bt.specific_annual_heating_demand(
        u_value=env_u,
        heating_degree_days=3497,
        heating_days=222,
        thermal_bridges_factor=0.1,
        ventilation_rate=0.6,
        irradiation_heating_season=403,
        gain_utilisation_factor=0.958363,
        transmittance_windows=0.6,
    )
    assert round(float(annual.sum()), 3) == 9405.615
    assert round(float(specific.sum()), 3) == 40.894


class TestUncoveredBranches:
    def test_check_type_none_passes_through(self):
        # line 14-15: the None branch of check_type
        assert szb.check_type(None) is None

    def test_empty_envelope_parameter(self):
        # All parts None -> df property empty branch (52-61),
        # flat_df None branch (77) and columns_flat=[] (85)
        env = szb.EnvelopeParameter()
        assert env.df is None
        assert env.flat_df is None
        assert env.correction_factors == {}

    def test_envelope_parameter_only_some_parts_concat(self):
        # Concat branch of df (only non-None parts are collected)
        wall = pd.DataFrame({"wall_1": [10, 12], "wall_2": [14, 16]})
        window = pd.DataFrame({"window_1": [4, 5]})
        env = szb.EnvelopeParameter(wall=wall, window=window)
        df = env.df
        assert isinstance(df.columns, pd.MultiIndex)
        assert df["wall"].shape == (2, 2)
        assert df["window"].shape == (2, 1)

    def test_from_dataframe_roundtrip(self):
        # line 46 (ea = cls()) and the column mapping loop
        df = pd.DataFrame(
            {"Wall": [10], "Tür": [3], "Dach": [20], "Boden": [15]}
        )
        env = szb.EnvelopeParameter.from_dataframe(df)
        assert float(env.window.iloc[0, 0]) == 3
        assert float(env.floor.iloc[0, 0]) == 15
        assert float(env.roof.iloc[0, 0]) == 20
        assert float(env.wall.iloc[0, 0]) == 10

    def test_heat_losses_ventilation_custom_air(self):
        # heat_losses_ventilation_building body with custom kwargs
        env = szb.EnvelopeParameter(floor=15, window=5, roof=20, wall=34)
        bt = szb.BuildingTable(
            area=env,
            conditioned_floor_area=230,
            floor_height=2.5,
            window_orientation_factor=0.7,
        )
        base = bt.heat_losses_ventilation_building(0.6, 100)
        custom = bt.heat_losses_ventilation_building(
            0.6, 100, recovery_factor=0.5, rho_air=1.5, heat_capacity_air=1.02
        )
        assert custom < base  # recovery reduces the loss

    def test_check_type_dataframe_branch(self):
        df = pd.DataFrame({"a": [1]})
        assert szb.check_type(df) is df

    def test_check_type_invalid_raises(self):
        with pytest.raises(TypeError, match="not supported"):
            szb.check_type(["not", "supported"])
        with pytest.raises(TypeError, match="not supported"):
            szb.check_type({"a": 1})

    def test_building_table_attribute_assignment(self):
        # lines 101/108: BuildingTable.__init__ assignments
        env = szb.EnvelopeParameter(floor=15, window=5, roof=20, wall=34)
        bt = szb.BuildingTable(
            area=env,
            conditioned_floor_area=230,
            floor_height=2.5,
            window_orientation_factor=0.7,
        )
        assert bt.area is env
        assert bt.conditioned_floor_area == 230
        assert bt.floor_height == 2.5
        assert bt.window_orientation_factor == 0.7

    def test_annual_heating_demand_dataframe_adjustment_factor(self):
        # DataFrames for every part -> multi-row building. This exercises:
        #  - line 346: DataFrame adjustment_factor branch
        #  - line 458: solar_gain else-branch (window as DataFrame)
        #  - line 468->470: solar_gain already a Series (body skipped)
        def part(col, values):
            return pd.DataFrame({col: values}, index=range(len(values)))

        area = szb.EnvelopeParameter(
            wall=part("wall", [34, 40]),
            window=part("window", [5, 6]),
            roof=part("roof", [20, 22]),
            floor=part("floor", [15, 16]),
        )
        u_value = szb.EnvelopeParameter(
            wall=part("wall", [0.5, 0.5]),
            window=part("window", [0.3, 0.3]),
            roof=part("roof", [0.5, 0.5]),
            floor=part("floor", [0.3, 0.3]),
        )
        bt = szb.BuildingTable(
            area=area,
            conditioned_floor_area=pd.Series([230, 250], index=[0, 1]),
            floor_height=pd.Series([2.5, 2.5], index=[0, 1]),
            window_orientation_factor=0.7,
        )
        common = dict(
            u_value=u_value,
            thermal_bridges_factor=0.1,
            ventilation_rate=0.6,
            transmittance_windows=0.6,
            gain_utilisation_factor=0.958363,
            heating_degree_days=3497,
            heating_days=222,
            irradiation_heating_season=403,
        )
        base = bt.annual_heating_demand(**common)
        # Ones-DataFrame with matching index/columns -> result unchanged
        adj = pd.DataFrame(1, index=base.index, columns=base.columns)
        adjusted = bt.annual_heating_demand(**common, adjustment_factor=adj)
        pd.testing.assert_frame_equal(adjusted, base)
