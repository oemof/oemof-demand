# -*- coding: utf-8 -*-

"""
Tests for the single zone building model.

SPDX-FileCopyrightText: Uwe Krien <uwe.krien@ifam.fraunhofer.de>
SPDX-License-Identifier: MIT
"""

import pandas as pd
import pytest

from oemof.demand.tabula import single_zone_building as szb


def test_heat_losses_transmission_component_scalar():
    """Example from the docstring: Q = A * U * HDD * 24 * 0.001."""
    result = szb.heat_losses_transmission_component(10, 5, 200)
    assert result == pytest.approx(240.0)


def test_heat_losses_transmission_component_correction_factor():
    result = szb.heat_losses_transmission_component(10, 5, 200, 0.5)
    assert result == pytest.approx(120.0)


def test_heat_losses_transmission_component_series():
    area = pd.Series([10, 20], index=[0, 1])
    u_value = pd.Series([5, 2], index=[0, 1])
    result = szb.heat_losses_transmission_component(area, u_value, 200)
    expected = area * u_value * 200 * 24 * 0.001
    pd.testing.assert_series_equal(result, expected)


class TestCheckType:
    def test_dataframe(self):
        df = pd.DataFrame({"a": [1]})
        assert isinstance(szb.check_type(df), pd.DataFrame)

    def test_float(self):
        assert szb.check_type(5.0) == 5.0

    def test_invalid_type(self):
        with pytest.raises(TypeError, match="not supported"):
            szb.check_type(["not", "supported"])


class TestEnvelopeParameter:
    def setup_method(self):
        self.env = szb.EnvelopeParameter(
            wall=34, window=5, roof=20, floor=15
        )

    def test_parts(self):
        assert self.env.parts == ["wall", "window", "roof", "floor"]

    def test_default_correction_factors(self):
        # Without explicit factors all missing parts should be set to 1.
        assert self.env.correction_factors == {
            "wall": 1,
            "window": 1,
            "roof": 1,
            "floor": 1,
        }

    def test_df_multilevel_for_scalars(self):
        df = self.env.df
        assert df.shape == (1, 4)
        assert isinstance(df.columns, pd.MultiIndex)
        assert df.loc[0, ("wall", "wall")] == 34

    def test_flat_df(self):
        df = self.env.flat_df
        assert list(df.columns) == ["wall", "window", "roof", "floor"]
        assert df.loc[0, "window"] == 5

    def test_add_correction_factors(self):
        self.env.add_correction_factors({"wall": 0.5})
        assert self.env.correction_factors["wall"] == 0.5

    def test_add_correction_factors_unknown_part(self):
        with pytest.raises(ValueError, match="not found in column list"):
            self.env.add_correction_factors({"ceiling": 0.5})

    def test_add_correction_factors_with_missing(self):
        self.env.add_correction_factors({"wall": 0.5}, add_missing=True)
        assert self.env.correction_factors == {
            "wall": 0.5,
            "window": 1,
            "roof": 1,
            "floor": 1,
        }

    def test_uses_area_keys_from_config(self):
        # The config defines 'tür/tuer/door' as window keys and 'boden' as
        # floor key. They must be picked up by from_dataframe().
        df = pd.DataFrame(
            {
                "Wall": [10],
                "Tür": [3],
                "Dach": [20],
                "Boden": [15],
            }
        )
        env = szb.EnvelopeParameter.from_dataframe(df)
        assert float(env.window.iloc[0, 0]) == 3
        assert float(env.floor.iloc[0, 0]) == 15


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

    def test_heat_losses_ventilation_building(self):
        # mass_flow = 230 * 2.5 * 0.6 * 1.2 = 414
        # Q = 1.020 / 3600 * 414 * 24 * HDD
        hdd = 3497
        expected = (1.020 / 3600) * 414 * 24 * hdd
        result = self.bt.heat_losses_ventilation_building(0.6, hdd)
        assert result == pytest.approx(expected)

    def test_heat_losses_ventilation_recovery(self):
        base = self.bt.heat_losses_ventilation_building(0.6, 100)
        with_recovery = self.bt.heat_losses_ventilation_building(
            0.6, 100, recovery_factor=0.5
        )
        assert with_recovery == pytest.approx(base * 0.5)

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
        expected_cols = [
            "wall",
            "window",
            "roof",
            "floor",
            "thermal bridges",
            "ventilation",
        ]
        assert list(losses.columns) == expected_cols

    def test_internal_heat_sources(self):
        # From docstring: with conditioned area 230 and 222 heating days.
        env = pd.DataFrame(
            {"door": 2, "window": 5, "roof": 20, "wall": 4}, index=[0]
        )
        area = pd.Series(data=[230], index=[0])
        height = pd.Series(data=[2.5], index=[0])
        orient = pd.Series(data=[0.7], index=[0])
        bt = szb.BuildingTable(
            area=env,
            conditioned_floor_area=area,
            floor_height=height,
            window_orientation_factor=orient,
        )
        sg = bt.internal_heat_sources(222)
        assert round(float(sg[0]), 2) == 3455.74
        assert round(float((sg / bt.conditioned_floor_area)[0]), 2) == 15.02

    def test_solar_gain_series(self):
        result = self.bt.solar_gain(400, 0.6, 0.94)
        assert isinstance(result, pd.Series)
        assert result.name == "solar gain"

    def test_solar_gain_with_dataframe_area(self):
        env = szb.EnvelopeParameter(
            floor=2, window=5, roof=20, wall=4
        )
        bt = szb.BuildingTable(
            area=env,
            conditioned_floor_area=pd.Series(data=[230], index=[0]),
            floor_height=pd.Series(data=[2.5], index=[0]),
            window_orientation_factor=pd.Series(data=[0.7], index=[0]),
        )
        sg = bt.solar_gain(400, 0.6, 0.94)
        # Docstring example result.
        assert round(float(sg[0]), 2) == 298.47
        assert round(float((sg / bt.conditioned_floor_area)[0]), 2) == 1.3

    def test_annual_heating_demand(self):
        result = self.bt.annual_heating_demand(
            u_value=self.env_u,
            thermal_bridges_factor=0.1,
            ventilation_rate=0.6,
            transmittance_windows=0.6,
            gain_utilisation_factor=0.958363,
            heating_degree_days=3497,
            heating_days=222,
            irradiation_heating_season=403,
        )
        # Docstring example result.
        assert round(float(result.sum()), 3) == 9405.615

    def test_specific_annual_heating_demand(self):
        result = self.bt.specific_annual_heating_demand(
            u_value=self.env_u,
            thermal_bridges_factor=0.1,
            ventilation_rate=0.6,
            transmittance_windows=0.6,
            gain_utilisation_factor=0.958363,
            heating_degree_days=3497,
            heating_days=222,
            irradiation_heating_season=403,
        )
        # Docstring example result.
        assert round(float(result.sum()), 3) == 40.894

    def test_adjustment_factor(self):
        result = self.bt.annual_heating_demand(
            u_value=self.env_u,
            thermal_bridges_factor=0.1,
            ventilation_rate=0.6,
            transmittance_windows=0.6,
            gain_utilisation_factor=0.958363,
            heating_degree_days=3497,
            heating_days=222,
            irradiation_heating_season=403,
            adjustment_factor=2,
        )
        base = self.bt.annual_heating_demand(
            u_value=self.env_u,
            thermal_bridges_factor=0.1,
            ventilation_rate=0.6,
            transmittance_windows=0.6,
            gain_utilisation_factor=0.958363,
            heating_degree_days=3497,
            heating_days=222,
            irradiation_heating_season=403,
        )
        # A single-row result is returned squeezed to a Series.
        pd.testing.assert_series_equal(result, base * 2)
