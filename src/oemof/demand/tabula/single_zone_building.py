"""
https://www.energie-experten.org/bauen-und-sanieren/daemmung/waermedaemmung/transmissionswaermeverlust

"""

import pandas as pd

from oemof.demand import config as cfg


def check_type(data):
    if isinstance(data, pd.DataFrame):
        return data
    if data is None:
        return data
    try:
        data = float(data)
    except TypeError:
        pass
    if isinstance(data, float):
        return data
    else:
        raise TypeError(
            f"Type {type(data)} is not supported. Use a scalr Value or a "
            f"pandas.DataFrame instead."
        )


class EnvelopeParameter:
    def __init__(
        self,
        wall=None,
        window=None,
        roof=None,
        floor=None,
        correction_factors=None,
    ):
        self.wall = check_type(wall)
        self.window = check_type(window)
        self.roof = check_type(roof)
        self.floor = check_type(floor)
        self.parts = ["wall", "window", "roof", "floor"]
        self._df = None
        self._flat_df = None
        if correction_factors is not None:
            self.add_correction_factors(correction_factors)
        else:
            self.add_correction_factors({}, add_missing=True)

    @classmethod
    def from_dataframe(cls, df):
        ea = cls()
        keys = cfg.get_dict_list("area_keys")
        for part in ea.parts:
            cols = [
                c
                for c in df.columns
                if len([k for k in keys[part] if k in c.lower()]) > 0
            ]
            setattr(ea, part, df[cols])
        return ea

    @property
    def df(self):
        """
        Returns
        -------
        pandas.DataFrame
        """
        if self._df is None:
            all_df = {
                k: getattr(self, k)
                for k in self.parts
                if getattr(self, k) is not None
            }
            if len(all_df) == 0:
                return self._df
            elif all([isinstance(v, (float, int)) for v in all_df.values()]):
                df = pd.DataFrame(all_df, index=[0])
                df.columns = pd.MultiIndex.from_arrays(
                    [list(df.columns), list(df.columns)]
                )
                self._df = df
            else:
                self._df = pd.concat(
                    all_df.values(), keys=all_df.keys(), axis=1
                )
        return self._df

    @property
    def flat_df(self):
        """
        Returns
        -------
        pandas.DataFrame
        """
        if self._flat_df is None:
            if self.df is not None:
                self._flat_df = self.df.droplevel(0, axis=1)
            else:
                self._flat_df = None
        return self._flat_df

    def add_correction_factors(self, factors, add_missing=False):
        """ """

        if self.flat_df is None:
            columns_flat = []
        else:
            columns_flat = list(self.flat_df.columns)
        for factor in factors.keys():
            if factor not in columns_flat:
                msg = (
                    f"Part <{factor}> not found in column list {columns_flat}"
                )
                raise ValueError(msg)
        if add_missing:
            base = {c: 1 for c in columns_flat}
            base.update(factors)
            factors = base
        self.correction_factors = factors


class BuildingTable:
    def __init__(
        self,
        area,
        conditioned_floor_area,
        floor_height,
        window_orientation_factor,
    ):
        """

        Parameters
        ----------
        area : pandas.DataFrame or Enevelop
        conditioned_floor_area
        floor_height
        window_orientation_factor

        Examples
        --------
        >>> env_area=EnvelopeParameter(floor=15, window=5, roof=20, wall=34)
        >>> bt = BuildingTable(
        ...    area= env_area,
        ...    conditioned_floor_area=230,
        ...    floor_height=2.5,
        ...    window_orientation_factor=0.7)
        >>> bt.floor_height
        2.5
        >>> env_u_values=EnvelopeParameter(
        ...     wall=0.5, roof=0.5, window=0.3, floor=0.3)
        >>> round(float(bt.annual_heating_demand(
        ...     u_value=env_u_values,
        ...     heating_degree_days=3497,
        ...     heating_days=222,
        ...     thermal_bridges_factor=0.1,
        ...     ventilation_rate=0.6,
        ...     irradiation_heating_season=403,
        ...     gain_utilisation_factor=0.958363,
        ...     transmittance_windows=0.6
        ... ).sum()),3)
        9405.615
        >>> round(float(bt.specific_annual_heating_demand(
        ...     u_value=env_u_values,
        ...     heating_degree_days=3497,
        ...     heating_days=222,
        ...     thermal_bridges_factor=0.1,
        ...     ventilation_rate=0.6,
        ...     irradiation_heating_season=403,
        ...     gain_utilisation_factor=0.958363,
        ...     transmittance_windows=0.6
        ... ).sum()),3)
        40.894
        """
        self.area = area
        self.conditioned_floor_area = conditioned_floor_area
        self.floor_height = floor_height
        self.window_orientation_factor = window_orientation_factor

    def heat_losses_ventilation_building(
        self,
        ventilation_rate,
        heating_degree_day,
        recovery_factor=0,
        rho_air=1.2,
        heat_capacity_air=1.020,
    ):
        """

        Parameters
        ----------
        ventilation_rate
        heating_degree_day
        recovery_factor
        rho_air
        heat_capacity_air : float
            The default value of 1.02 kJ/(m³*K)

        Returns
        -------

        """
        volume = self.conditioned_floor_area * self.floor_height
        # m³ * 1/h * kg/m³ -> kg/h
        mass_flow = volume * ventilation_rate * rho_air

        # kJ/(kg*K)
        # / kWh/kJ
        # * kg/h
        # * h/d
        # * Kd
        # -> kWh
        return (
            heat_capacity_air
            / 3600
            * mass_flow
            * 24
            * heating_degree_day
            * (1 - recovery_factor)
        )

    def heat_losses_building(
        self,
        u_value,
        heating_degree_days,
        ventilation_rate,
        thermal_bridges_factor,
        **kwargs,
    ):
        """

        Parameters
        ----------
        u_value
        heating_degree_days
        ventilation_rate
        thermal_bridges_factor

        Notes
        -----
        kwargs will be passed to the method `heat_losses_ventilation_building`.


        Returns
        -------

        """
        heat_losses = {}
        for building_part in self.area.flat_df.columns:
            heat_losses[building_part] = heat_losses_transmission_component(
                self.area.flat_df[building_part],
                u_value[building_part],
                heating_degree_days,
                correction_factor=self.area.correction_factors[building_part],
            )
        heat_losses["thermal bridges"] = self.thermal_bridges(
            heating_degree_days * 24 * 0.001, thermal_bridges_factor
        )
        heat_losses["ventilation"] = self.heat_losses_ventilation_building(
            ventilation_rate, heating_degree_days, **kwargs
        )
        return pd.DataFrame(heat_losses)

    def specific_annual_heating_demand(
        self,
        u_value,
        thermal_bridges_factor,
        ventilation_rate,
        transmittance_windows,
        gain_utilisation_factor,
        heating_degree_days,
        heating_days,
        irradiation_heating_season,
        adjustment_factor=1,
    ):
        return self.annual_heating_demand(
            u_value=u_value,
            thermal_bridges_factor=thermal_bridges_factor,
            ventilation_rate=ventilation_rate,
            transmittance_windows=transmittance_windows,
            gain_utilisation_factor=gain_utilisation_factor,
            heating_degree_days=heating_degree_days,
            heating_days=heating_days,
            irradiation_heating_season=irradiation_heating_season,
            adjustment_factor=adjustment_factor,
        ).div(self.conditioned_floor_area, axis=0)

    def thermal_bridges(self, heating_degree_days, thermal_bridges_factor):
        """Simple approach with a constant factor W/(m2*K) [envelope area]."""
        return (
            self.area.df.sum(axis=1)
            * thermal_bridges_factor
            * heating_degree_days
        )

    def annual_heating_demand(
        self,
        u_value,
        thermal_bridges_factor,
        ventilation_rate,
        transmittance_windows,
        gain_utilisation_factor,
        heating_degree_days,
        heating_days,
        irradiation_heating_season,
        adjustment_factor=1,
    ):
        """

        Parameters
        ----------
        irradiation_heating_season
        heating_days
        heating_degree_days
        u_value
        thermal_bridges_factor
        ventilation_rate
        transmittance_windows
        gain_utilisation_factor
        adjustment_factor

        Returns
        -------

        """
        df_loss = self.heat_losses_building(
            u_value.flat_df,
            heating_degree_days,
            ventilation_rate,
            thermal_bridges_factor,
        )
        sources = self.internal_heat_sources(
            heating_days,
            utilisation_factor=gain_utilisation_factor,
        ) * (-1)
        solar_gain = self.solar_gain(
            irradiation_heating_season,
            transmittance_windows,
            utilisation_factor=gain_utilisation_factor,
            orientation_factor=self.window_orientation_factor,
        ) * (-1)

        annual_demand = pd.concat([sources, df_loss, solar_gain], axis=1)
        if isinstance(adjustment_factor, pd.DataFrame):
            adjustment_factor = adjustment_factor

        return annual_demand.mul(adjustment_factor, axis=0).squeeze()

    def internal_heat_sources(
        self,
        heating_days,
        utilisation_factor=0.94,
        specific_internal_heat_gain=3,
    ):
        """
        Simple approach for internal heat gain calculation

        Parameters
        ----------
        heating_days : float
        utilisation_factor : float
        specific_internal_heat_gain : float

        Returns
        -------
        pandas.Series

        Examples
        --------
        >>> env_area=pd.DataFrame({"door":2, "window":5, "roof": 20, "wall":4},
        ...                       index=[0])
        >>> bt = BuildingTable(
        ...    area= env_area,
        ...    conditioned_floor_area=pd.Series(data=[230], index=[0]),
        ...    floor_height=pd.Series(data=[2.5], index=[0]),
        ...    window_orientation_factor=pd.Series(data=[0.7], index=[0]))
        >>> sg = bt.internal_heat_sources(222)
        >>> float(round(sg[0], 2))
        3455.74
        >>> float(round((sg/bt.conditioned_floor_area)[0], 2))
        15.02

        """
        ihc = (
            0.024
            * specific_internal_heat_gain
            * heating_days
            * self.conditioned_floor_area
        )
        ihc = ihc * utilisation_factor
        if not isinstance(ihc, pd.Series):
            ihc = pd.Series(ihc)
        ihc.name = "internal heat sources"
        return ihc

    def solar_gain(
        self,
        global_radiation_horizontal,
        transmittance_factor,
        utilisation_factor,
        orientation_factor=0.7,
        ext_shading=0.6,
        frame_fraction=0.3,
        non_perpendicular_fraction=0.9,
    ):
        """
        Solar gain that reduces the heating demand in buildings.

        Parameters
        ----------
        global_radiation_horizontal : float
            Global irradiation on a horiontal surface.
        transmittance_factor : float
            Average transmittance factor of the windows.
        utilisation_factor : float
            Effective heat gain used as a reduction of the heating demand.
        orientation_factor : float
            Distribution of the windows in different directions (default: 0.7)
        ext_shading : float
            Generic factor for the reduction of the irradiation due to shading
            (default: 0.6)
        frame_fraction : float
            Fraction of the window frame (default: 0.3)
        non_perpendicular_fraction :  float
            Statistical reduction due to non-perpendicular windows
            (default: 0.9)

        Returns
        -------
        pandas.Series

        Examples
        --------
        >>> env_area=EnvelopeParameter(floor=2, window=5, roof=20, wall=4)
        >>> bt = BuildingTable(
        ...    area= env_area,
        ...    conditioned_floor_area=pd.Series(data=[230], index=[0]),
        ...    floor_height=pd.Series(data=[2.5], index=[0]),
        ...    window_orientation_factor=pd.Series(data=[0.7], index=[0]))
        >>> sg = bt.solar_gain(400, 0.6, 0.94)
        >>> float(round(sg[0], 2))
        298.47
        >>> float(round((sg/bt.conditioned_floor_area)[0], 2))
        1.3
        """
        squeeze_to_series(
            [
                global_radiation_horizontal,
                transmittance_factor,
                utilisation_factor,
                orientation_factor,
            ]
        )
        if isinstance(self.area.window, (float, int)):
            area_w = self.area.window
        else:
            area_w = self.area.window.sum(axis=1)
        solar_gain = (
            ext_shading
            * (1 - frame_fraction)
            * non_perpendicular_fraction
            * transmittance_factor
            * area_w
            * global_radiation_horizontal
            * orientation_factor
        ) * utilisation_factor
        if not isinstance(solar_gain, pd.Series):
            solar_gain = pd.Series(solar_gain)
        solar_gain.name = "solar gain"
        return solar_gain


def heat_losses_transmission_component(
    area, u_value, heating_degree_day, correction_factor=1
):
    """
    Transmission losses, knowing the U-value and the heating_hours.

    Parameters
    ----------
    area : numeric or pandas.Series
        Surface of the element [m²].
    u_value : numeric or pandas.Series
        U-value of the element [W/(K*m²)]
    heating_degree_day : numeric or pandas.Series
        The heating degree days of the region [Kd] (Kelvin days). This value
        will be multiplied with 24 h/d to get a demand of Wh instead of Wd.
    correction_factor : numeric or pandas.Series

    Returns
    -------
    float

    Examples
    --------
    >>> heat_losses_transmission_component(10, 5, 200)
    240.0
    """

    heating_hours = heating_degree_day * 24  # K*d * h/d -> K*h
    # unit_factor: 0,001 kW/W
    unit_factor = 0.001
    return area * u_value * heating_hours * correction_factor * unit_factor


def squeeze_to_series(args):
    for a in args:
        if isinstance(a, pd.DataFrame):
            a.squeeze()
