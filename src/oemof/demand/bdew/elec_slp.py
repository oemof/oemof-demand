# -*- coding: utf-8 -*-
"""
Implementation of the standard load profiles

SPDX-FileCopyrightText: Birgit Schachler
SPDX-FileCopyrightText: Uwe Krien <krien@uni-bremen.de>
SPDX-FileCopyrightText: jnnr
SPDX-FileCopyrightText: Stephen Bosch
SPDX-FileCopyrightText: Patrik Schönfeldt

SPDX-License-Identifier: MIT
"""

import calendar
import datetime
import os
import warnings

import pandas as pd

from oemof.demand.tools import add_weekdays2df

from ._profiles25 import _bdew_datapath


def dynamisation_function(timeindex: pd.DatetimeIndex) -> pd.Series:
    r"""
    Use the dynamisation function of the BDEW to smoothen the seasonal
    edges. Functions resolution is daily.

        .. math::
            F_t = -3,92\cdot10^{-10} \cdot t^4 + 3,2\cdot10^{-7}
            \cdot t^3– 7,02\cdot10^{-5}\cdot t^2 + 2,1\cdot10^{-3}
            \cdot t + 1,24

    With `t` the day of the year as a decimal number.
    """

    # The standard sais that the day of the year (1 through 365)
    # should be used. However, normalisation works better if we
    # allow fractional days and start by day 0.
    day_of_year = pd.Series(
        [((q + 1) / (24 * 4)) for q in range(len(timeindex))],
        index=timeindex,
    )

    # Calculate the smoothing factor of the BDEW dynamic H0 profile
    # Adjustment of for normalisation: from -3,92 to -3.916649251
    return pd.Series(
        -3.916649251 * 10**-10 * day_of_year**4
        + 3.2 * 10**-7 * day_of_year**3
        - 7.02 * 10**-5 * day_of_year**2
        + 0.0021 * day_of_year
        + 1.24,
        index=timeindex,
    )


class ElecSlp:
    """Generate electrical standardized load profiles based on the BDEW method.

    Parameters
    ----------
    year : integer
        Year of the demand series.

    Optional Parameters
    -------------------
    seasons : dictionary
        Describing the time ranges for summer, winter and transition periods.
        The seasons dictionary will update the existing one, so only changed
        keys have to be defined. Make sure not to create time gaps. The
        "h0_dyn" will not work with changed seasons, so you have to use your
        own smoothing curve to create a "h0_dyn" profile.
    holidays : dictionary or list
        The keys of the dictionary or the items of the list should be datetime
        objects of the days that are holidays.
    """

    def __init__(self, year, seasons=None, holidays=None):
        if calendar.isleap(year):
            hoy = 8784
        else:
            hoy = 8760
        self._date_time_index = pd.date_range(
            datetime.datetime(year, 1, 1, 0), periods=hoy * 4, freq="15Min"
        )
        if seasons is None:
            self._seasons = {
                "summer1": [5, 15, 9, 14],  # summer: 15.05. to 14.09
                "transition1": [3, 21, 5, 14],  # transition1 :21.03. to 14.05
                "transition2": [9, 15, 10, 31],  # transition2 :15.09. to 31.10
                "winter1": [1, 1, 3, 20],  # winter1:  01.01. to 20.03
                "winter2": [11, 1, 12, 31],  # winter2: 01.11. to 31.12
            }
        else:
            self._seasons = seasons
        self.year = year
        # Create the default profiles
        self.slp_frame = self.all_load_profiles(
            self._date_time_index, holidays=holidays
        )
        # Add the dynamic H0 profile
        self.create_dynamic_h0_profile()

    @property
    def date_time_index(self):
        return self._date_time_index

    def all_load_profiles(self, time_df, holidays=None):
        slp_types = [
            "h0",
            "g0",
            "g1",
            "g2",
            "g3",
            "g4",
            "g5",
            "g6",
            "l0",
            "l1",
            "l2",
        ]
        new_df = self.create_bdew_load_profiles(
            time_df, slp_types, holidays=holidays
        )

        return new_df

    def create_bdew_load_profiles(self, dt_index, slp_types, holidays=None):
        """
        Calculates the hourly electricity load profile in MWh/h of a region.
        """

        # define file path of slp csv data
        file_path = os.path.join(_bdew_datapath, "selp_series.csv")

        # Read standard load profile series from csv file
        selp_series = pd.read_csv(file_path)
        tmp_df = selp_series
        # Create an index to merge. The year and month will be ignored only the
        # time index is necessary.
        index = pd.date_range(
            datetime.datetime(2007, 1, 1, 0), periods=2016, freq="15Min"
        )
        tmp_df.set_index(index, inplace=True)

        # Create empty DataFrame to take the results.
        new_df = pd.DataFrame(data=0, index=dt_index, columns=slp_types)
        new_df = add_weekdays2df(
            new_df, holidays=holidays, holiday_is_sunday=True
        )

        new_df["hour"] = dt_index.hour
        new_df["minute"] = dt_index.minute
        profile_columns = [
            c for c in new_df.columns if "g" in c or "h0" in c or "l" in c
        ]
        new_df[profile_columns] = new_df[profile_columns].map(float)

        time_df = new_df[["date", "hour", "minute", "weekday"]].copy()
        tmp_df[slp_types] = tmp_df[slp_types].astype(float)

        # Inner join the slps on the time_df to the slp's for a whole year
        tmp_df["hour_of_day"] = tmp_df.index.hour
        tmp_df["minute_of_hour"] = tmp_df.index.minute
        left_cols = ["hour_of_day", "minute_of_hour", "weekday"]
        right_cols = ["hour", "minute", "weekday"]
        tmp_df = tmp_df.reset_index(drop=True)

        for p in self._seasons.keys():
            a = datetime.datetime(
                self.year, self._seasons[p][0], self._seasons[p][1], 0, 0
            )
            b = datetime.datetime(
                self.year, self._seasons[p][2], self._seasons[p][3], 23, 59
            )
            merged_df = pd.DataFrame.merge(
                tmp_df[tmp_df["period"] == p[:-1]],
                time_df[a:b],
                left_on=left_cols,
                right_on=right_cols,
                how="inner",
            ).drop(labels=["hour_of_day"], axis=1)

            merged_df.index = (
                pd.to_datetime(merged_df["date"])
                + pd.to_timedelta(merged_df["hour"], unit="h")
                + pd.to_timedelta(merged_df["minute"], unit="m")
            )
            merged_df.sort_index(inplace=True)
            new_df.update(merged_df[profile_columns])

        new_df.drop(
            ["date", "minute", "hour", "weekday"], axis=1, inplace=True
        )
        return new_df.div(new_df.sum(axis=0), axis=1)

    def create_dynamic_h0_profile(self):
        # Multiply the smoothing factor with the static H0 profile
        self.slp_frame["h0_dyn"] = self.slp_frame["h0"].mul(
            dynamisation_function(self.slp_frame.index), axis=0
        )
        return self.slp_frame["h0_dyn"]

    def get_profile(self, ann_el_demand_per_sector):
        """
        DEPRECATED: Use :py:meth:`~get_scaled_power_profiles()` instead

        Parameters
        ----------
        ann_el_demand_per_sector : dictionary
            Key: sector, value: annual value

        Returns
        -------
        pandas.DataFrame : Table with all profiles

        """
        msg = (
            "This method is deprecated and will be removed in future "
            "versions\nUse the method get_scaled_power_profiles() instead."
        )
        warnings.warn(msg, FutureWarning)
        return (
            self.slp_frame.multiply(
                pd.Series(ann_el_demand_per_sector), axis=1
            ).dropna(how="all", axis=1)
            * 4
        )

    def get_profiles(self, *args):
        """Get all or the selected profiles. To select profiles you can pass
         the name of the types as strings. The profiles are normalised to 1.

        Try `print(get_profiles().columns` to get all valid types.

        Returns
        -------
        pandas.DataFrame : Table with all or the selected profiles.

        Examples
        --------
        >>> from oemof.demand import bdew
        >>> e_slp = bdew.ElecSlp(year=2020)
        >>> ", ".join(sorted(e_slp.get_profiles().columns))
        'g0, g1, g2, g3, g4, g5, g6, h0, h0_dyn, l0, l1, l2'
        >>> e_slp.get_profiles("h0", "g0").head()
                                   h0        g0
        2020-01-01 00:00:00  0.000017  0.000016
        2020-01-01 00:15:00  0.000015  0.000015
        2020-01-01 00:30:00  0.000014  0.000015
        2020-01-01 00:45:00  0.000012  0.000014
        2020-01-01 01:00:00  0.000012  0.000013

        >>> e_slp.get_profiles("h0", "g0").sum()
        h0    1.0
        g0    1.0
        dtype: float64
        """
        if len(args) == 0:
            return self.slp_frame
        else:
            return self.slp_frame[list(args)]

    def get_scaled_profiles(self, ann_el_demand_per_sector):
        """Get profiles scaled by there annual value.

        Parameters
        ----------
        ann_el_demand_per_sector : dict
            The annual demand in an energy unit for each type.

        Returns
        -------
        pandas.DataFrame : Table with scaled profiles.

        Examples
        --------
        >>> from oemof.demand import bdew
        >>> e_slp = bdew.ElecSlp(year=2020)
        >>> e_slp.get_scaled_profiles({"h0": 3000, "g0": 5000}).head()
                                   g0        h0
        2020-01-01 00:00:00  0.080084  0.050657
        2020-01-01 00:15:00  0.076466  0.045591
        2020-01-01 00:30:00  0.072897  0.041125
        2020-01-01 00:45:00  0.069671  0.037408
        2020-01-01 01:00:00  0.067030  0.034650

        >>> e_slp.get_scaled_profiles({"h0": 3000, "g0": 5000}).sum()
        g0    5000.0
        h0    3000.0
        dtype: float64
        """

        return self.slp_frame.multiply(
            pd.Series(ann_el_demand_per_sector), axis=1
        ).dropna(how="all", axis=1)

    def get_scaled_power_profiles(
        self, ann_el_demand_per_sector, conversion_factor=4
    ):
        """
        Get profiles scaled by there annual value. Each value represents
        the average power of an interval. Therefore, it is not possible to
        sum up the array. A conversion factor is used to calculate power
        units from energy units. By default the conversion factor is `4`. As
        the interval of each profile is 15 minutes a conversion factor of `4`
        will convert energy units like Wh, kWh, MWh etc. to power units like W,
        kW, MW etc..

        Parameters
        ----------
        ann_el_demand_per_sector : dict
            The annual demand in an energy unit for each type.
        conversion_factor : float
            Factor to convert the energy unit of the annual value to the
            power unit of each interval.

        Returns
        -------
        pandas.DataFrame : Table with scaled profiles.

        Examples
        --------
        >>> from oemof.demand import bdew
        >>> e_slp = bdew.ElecSlp(year=2020)
        >>> e_slp.get_scaled_power_profiles({"h0": 3000, "g0": 5000}).head()
                                   g0        h0
        2020-01-01 00:00:00  0.320338  0.202627
        2020-01-01 00:15:00  0.305866  0.182365
        2020-01-01 00:30:00  0.291590  0.164500
        2020-01-01 00:45:00  0.278682  0.149633
        2020-01-01 01:00:00  0.268122  0.138602
        >>> cf = 4
        >>> spp = e_slp.get_scaled_power_profiles({"h0": 3000, "g0": 5000},
        ...                                       conversion_factor=cf)
        >>> spp.sum()
        g0    20000.0
        h0    12000.0
        dtype: float64
        >>> spp.div(cf).sum()
        g0    5000.0
        h0    3000.0
        dtype: float64
        """
        return (
            self.get_scaled_profiles(ann_el_demand_per_sector)
            * conversion_factor
        )
