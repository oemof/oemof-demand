# -*- coding: utf-8 -*-
"""
Implementation of the 2025 BDEW standard load profiles:
* G25 (static), industrial profile based on 2022 and 2023 data
* H25 (dynamic), household profile based on 2018 and 2019 data
* L25 (static), farm profile based on previous L0 profile
* P25 (dynamic), profile for households with PV based on 2022 and 2023 data
* S25 (dynamic), profile for households with BES based on 2022 and 2023 data

SPDX-FileCopyrightText: Deutsches Zentrum für Luft- und Raumfahrt
SPDX-FileCopyrightText: Patrik Schönfeldt

SPDX-License-Identifier: MIT
"""

import os

import numpy as np
import pandas as pd

from oemof.demand.tools import set_holidays_in_df

_bdew_datapath = os.path.join(os.path.dirname(__file__), "bdew_data")


class BDEW25Profile(pd.Series):
    """
    Electrical standard load profiles based on the BDEW method (2025 revision)

    Note that we scale these profiles to be in units of power (values in kW),
    meaning the integral (not the sum) over one year will be 1 GWh.
    (For the default resolution of 15 minutes, this makes a factor of four.)

    Parameters
    ----------
    timeindex : pd.DatetimeIndex
        Time index to produce the SLP for. Only constant step-size is
        supported, i.e. timeindex.freq needs to be defined. For an index
        starting on a quarter hour, a 15-minute step reproduces the original
        SLP. Coarser steps average the quarter-hour values with timestamps
        in each interval. Finer steps pad those values because the SLP is
        constant within each quarter hour.

    Optional Parameters
    -------------------
    holidays : dictionary or list
        The keys of the dictionary or the items of the list should be datetime
        objects of the days that are holidays.
    """

    def __init__(
        self,
        timeindex: pd.DatetimeIndex,
        holidays: dict | list | None = None,
    ):
        original_timedelta = pd.Timedelta(timeindex.freq)
        profile_timedelta = pd.Timedelta(minutes=15)
        if original_timedelta == profile_timedelta:
            timeindex15m = timeindex
        else:
            end = timeindex[-1]
            inclusive = "both"
            if original_timedelta > profile_timedelta:
                end = pd.date_range(end, periods=2, freq=timeindex.freq)[1]
                inclusive = "left"
            timeindex15m = pd.date_range(
                start=timeindex[0],
                end=end,
                freq=profile_timedelta,
                inclusive=inclusive,
            )
        new_df = pd.DataFrame(
            data={
                "month": timeindex15m.month,
                "weekday": timeindex15m.day_of_week + 1,
                "hour": timeindex15m.hour,
                "minute": timeindex15m.minute,
            },
            index=timeindex15m,
        )

        set_holidays_in_df(new_df, holidays=holidays)

        new_df.replace({"weekday": [1, 2, 3, 4, 5]}, "WT", inplace=True)
        new_df.replace({"weekday": [6]}, "SA", inplace=True)
        new_df.replace(
            {"weekday": [0, 7]}, "FT", inplace=True
        )  # 0 for holiday

        new_df = new_df.merge(
            self.raw_profile_data,
            on=["month", "weekday", "hour", "minute"],
            how="inner",
        )
        new_df = new_df.set_index(timeindex15m)

        values = new_df.value
        if original_timedelta > profile_timedelta:
            interval_positions = timeindex.get_indexer(
                timeindex15m, method="pad"
            )
            values = values.groupby(timeindex[interval_positions]).mean()
        elif original_timedelta < profile_timedelta:
            values = values.reindex(timeindex, method="ffill")

        super().__init__(data=values, index=timeindex)

    @property
    def datafile(self):
        raise NotImplementedError(
            "BDEW25Profile needs to be implemented,"
            " please use one of its children instead."
        )

    @property
    def raw_profile_data(self):
        profile_data = pd.read_csv(
            _bdew_datapath + self.datafile,
            header=[0, 1],
        )

        profile_data = profile_data.rename(
            columns={
                "Januar": 1,
                "Februar": 2,
                "März": 3,
                "April": 4,
                "Mai": 5,
                "Juni": 6,
                "Juli": 7,
                "August": 8,
                "September": 9,
                "Oktober": 10,
                "November": 11,
                "Dezember": 12,
            },
        )
        del profile_data[("Unnamed: 0_level_0", "[kWh]")]

        hours = [h for h in range(24) for _ in range(4)]
        minutes = [m for _ in range(24) for m in range(0, 60, 15)]
        serialised_data = []
        for column in profile_data.columns:
            serialised_data.append(
                pd.DataFrame(
                    data={
                        "month": column[0],
                        "weekday": column[1],
                        "hour": hours,
                        "minute": minutes,
                        "value": 4 * profile_data[column],
                    }
                )
            )

        profile_data = pd.concat(serialised_data, ignore_index=True)
        return profile_data


class DynamicBDEW25Profile(BDEW25Profile):
    """
    BDEW25 SLP considering the dynamisation_function.
    See BDEW25Profile for more details.
    """

    def __init__(
        self, timeindex: pd.DatetimeIndex, holidays: dict | list | None = None
    ):
        super().__init__(timeindex=timeindex, holidays=holidays)
        self.update(self * self.dynamisation_function(timeindex))

    @staticmethod
    def dynamisation_function(timeindex: pd.DatetimeIndex) -> pd.Series:
        # cast to float hear because of miscalculations when using integers
        day_of_year = np.array(timeindex.day_of_year, dtype=float)

        return pd.Series(
            -3.92 * 10**-10 * day_of_year**4
            + 3.2 * 10**-7 * day_of_year**3
            - 7.02 * 10**-5 * day_of_year**2
            + 0.0021 * day_of_year
            + 1.24,
            index=timeindex,
        )


class G25(BDEW25Profile):
    """
    SLP for industries, see BDEW25Profile for more details.
    """

    def __init__(
        self, timeindex: pd.DatetimeIndex, holidays: dict | list | None = None
    ):
        super().__init__(timeindex=timeindex, holidays=holidays)

    @property
    def datafile(self):
        return "/g25.csv"


class H25(DynamicBDEW25Profile):
    """
    SLP for households, see DynamicBDEW25Profile for more details.
    """

    def __init__(
        self, timeindex: pd.DatetimeIndex, holidays: dict | list | None = None
    ):
        super().__init__(timeindex=timeindex, holidays=holidays)

    @property
    def datafile(self):
        return "/h25.csv"


class L25(BDEW25Profile):
    """
    SLP for farms, see BDEW25Profile for more details.
    """

    def __init__(
        self, timeindex: pd.DatetimeIndex, holidays: dict | list | None = None
    ):
        super().__init__(timeindex=timeindex, holidays=holidays)

    @property
    def datafile(self):
        return "/l25.csv"


class P25(DynamicBDEW25Profile):
    """
    SLP for housholds with generic PV system,
    see DynamicBDEW25Profile for more details.
    """

    def __init__(
        self, timeindex: pd.DatetimeIndex, holidays: dict | list | None = None
    ):
        super().__init__(timeindex=timeindex, holidays=holidays)

    @property
    def datafile(self):
        return "/p25.csv"


class S25(DynamicBDEW25Profile):
    """
    SLP for housholds with generic PV system and battery storage,
    see DynamicBDEW25Profile for more details.
    """

    def __init__(
        self, timeindex: pd.DatetimeIndex, holidays: dict | list | None = None
    ):
        super().__init__(timeindex=timeindex, holidays=holidays)

    @property
    def datafile(self):
        return "/s25.csv"
