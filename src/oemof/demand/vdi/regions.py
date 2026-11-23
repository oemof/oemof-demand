"""
The region module combines profiles from VDI 4655 for heat and power demand of
houses within one region.

This is an implementation of the calculation of load profiles
defined in the German VDI 4655.

    **VDI 4655**

    **Reference load profiles of single-family and
    multi-family houses for the use of CHP systems**

    *May 2008 (ICS 91.140.10)*

    *Verein Deutscher Ingenieure e.V.*

    *VDI Standards Department*

    *VDI-Platz 1, 40468 Duesseldorf, Germany*

Reproduced with the kind permission of the Verein Deutscher Ingenieure e.V.

Notes
-----
This script creates full year energy demand time series of domestic buildings
for use in simulations. This is achieved by an implementation of the VDI 4655,
which gives sample energy demands for a number of typical days ('Typtage').
The energy demand contains heating, hot water and electricity.

For a given year, the typical days can be matched to the actual calendar days,
based on the following conditions:
- Season: summer, winter or transition
- Day: weekday or sunday (Or holiday, which counts as sunday)
- Cloud coverage: cloudy or not cloudy
- House type: single-family houses or multi-family houses (EFH or MFH)

SPDX-FileCopyrightText: Joris Zimmermann
SPDX-FileCopyrightText: Uwe Krien

SPDX-License-Identifier: MIT
"""

import calendar
import datetime
import os
import warnings
from collections import namedtuple

import pandas as pd

from oemof.demand.tools import add_weekdays2df
from oemof.demand.vdi import dwd_try


class Climate:
    """
    Climate object for VDI time series.

    Parameters
    ----------
    temperature : iterable of numbers
            The ambient temperature in the area as daily mean values. The
            number of values must equal 365 or 366 for a leap year. Use the
            TRY data if no temperature data is available.
    cloud_coverage : iterable of numbers
            The cloud coverage in the area as daily mean values. The
            number of values must equal 365 or 366 for a leap year.
    """

    def __init__(
        self,
        temperature=None,
        cloud_coverage=None,
        energy_factors=None,
    ):
        self.temperature = temperature
        self.cloud_coverage = cloud_coverage
        self.energy_factors = energy_factors

    def from_try_data(self, try_region, hoy=8760):
        if try_region not in list(range(1, 16)):
            raise ValueError(
                f">{try_region}< is not a valid number of a DWD TRY region."
            )
        fn_weather = os.path.join(
            os.path.dirname(__file__),
            "resources_weather",
            "TRY2010_{:02d}_Jahr.dat".format(try_region),
        )
        weather = dwd_try.read_dwd_weather_file(fn_weather)
        weather = (
            weather.set_index(
                pd.date_range(
                    datetime.datetime(2010, 1, 1, 0),
                    periods=hoy,
                    freq="h",
                )
            )
            .resample("D")
            .mean()
        )
        self.temperature = weather["TAMB"]

        weather.loc[weather["CCOVER"] >= 5, "cloud_category"] = "B"
        weather.loc[weather["CCOVER"] < 5, "cloud_category"] = "H"
        self.cloud_coverage = weather["cloud_category"]
        fn_energy_factors = os.path.join(
            os.path.dirname(__file__),
            "vdi_data",
            "VDI_4655_Typtag-Faktoren.csv",
        )
        self.energy_factors = pd.read_csv(
            fn_energy_factors,
            index_col=[0, 1, 2],
        ).loc[try_region]
        return self

    def check_attributes(self):
        missing = []
        for check_attr in ["temperature", "cloud_coverage", "energy_factors"]:
            if self.__getattribute__(check_attr) is None:
                missing.append(check_attr)

        if len(missing) > 0:
            raise AttributeError(
                "Climate object not complete. Set the following attribute:"
                "\n* temperature\n* cloud_coverage\n* energy_factors"
            )


class Region:
    """Define region-dependent boundary conditions for the load profiles.

    After adding houses to the region, the load profiles for each house
    can be generated.

    Parameters
    ----------
    year : int
        Year of the profile.
    seasons : dict (optional)
        The times of the seasons if fixed seasons are used. In the VDI
        norm seasons are defined by the daily average temperature: Winter
        below 5 degree Celsius, Spring between 5 and 15 degree Celsius and
        summer above 15 degree Celsius.
    holidays : dict or list (optional)
        In case of a dictionary the keys are datetime objects and the
        values are strings with the name of the holiday. Otherwise a list
        of datetime objects should be passed.
    houses : list (optional)
        A list of dictionaries in which each house is defined the
        dictionary need to have the following keys.
    resample_rule : str (optional)
        Time interval to resample the profile e.g. 1h (1 hour) or 15min.
        The value will be passed to the pandas resample method.
    zero_summer_heat_demand : bool (optional)
        Set heat demand on all summer days to zero. Per default,
        multi-family houses have a small heat demand even in summer.
        (This is not part of VDI 4655)
    """

    def __init__(
        self,
        year,
        climate,
        seasons=None,
        holidays=None,
        houses=None,
        resample_rule=None,
        zero_summer_heat_demand=False,
    ):
        """Initialize Region class."""
        if calendar.isleap(year):
            self.hoy = 8784
        else:
            self.hoy = 8760
        self._datapath = os.path.join(os.path.dirname(__file__), "bdew_data")

        self._seasons = {
            "summer1": [5, 15, 9, 14],  # summer: 15.05. to 14.09
            "transition1": [3, 21, 5, 14],  # transition1 :21.03. to 14.05
            "transition2": [9, 15, 10, 31],  # transition2 :15.09. to 31.10
            "winter1": [1, 1, 3, 20],  # winter1:  01.01. to 20.03
            "winter2": [11, 1, 12, 31],  # winter2: 01.11. to 31.12
        }

        if seasons is not None:
            self._seasons.update(seasons)
            self._set_season = "fix"
        else:
            self._set_season = "temperature"

        self._year = year
        climate.check_attributes()
        self.temperature = climate.temperature
        self.cloud_coverage = climate.cloud_coverage
        self.energy_factors = climate.energy_factors

        self.houses = []
        if houses is not None:
            self.add_houses(houses)

        self.temperature_limits = self._get_temperature_level_combinations()
        self.zero_summer_heat_demand = zero_summer_heat_demand
        self.type_days = {}
        self._load_profiles = {}
        self._holidays = holidays
        self._resample_rule = resample_rule

    def _resample_profiles(self, rule, tl):
        self._load_profiles[tl] = self._load_profiles[tl].resample(rule).sum()
        self.type_days[tl] = self.type_days[tl].resample(rule).first()

    def _get_temperature_level_combinations(self):
        t_limit = namedtuple("temperature_limit", "summer winter")
        return set(
            [
                t_limit(
                    summer=h.get("summer_temperature_limit", 15),
                    winter=h.get("winter_temperature_limit", 5),
                )
                for h in self.houses
            ]
        )

    def _get_typical_days(self, holidays, temperature_limit):
        """
        Find the code for the typical days from dwd. The code consists of three
        letters:

          1. Season: W (winter), S (summer), U (transition)
          2. Day of the week: W (weekday), S (sunday/holiday)
          3. Cloud coverage for winter and transition: B (covered), H (partly
             clouded/sunny)

        Parameters
        ----------
        holidays

        """
        # Create the default time index
        date_time_index = pd.date_range(
            datetime.datetime(self._year, 1, 1, 0),
            periods=int(self.hoy / 24),
            freq="D",
        )
        days = pd.DataFrame(index=date_time_index)

        # Set season by fixed dates
        for p in self._seasons:
            a = datetime.datetime(
                self._year, self._seasons[p][0], self._seasons[p][1], 0, 0
            )
            b = datetime.datetime(
                self._year, self._seasons[p][2], self._seasons[p][3], 23, 59
            )
            days.loc[a:b, "season_fix"] = p[:-1]

        # Set weekdays and holidays
        days = add_weekdays2df(days, holidays=holidays, holiday_is_sunday=True)
        days.pop("date")

        days["TAMB"] = self.temperature.values
        days["cloud_category"] = self.cloud_coverage.values

        # 1. Set first letter of type days (season) from fixed season or season
        # by temperature.
        seasons_dict = {
            "summer": "S",
            "winter": "W",
            "transition": "U",
        }
        days.replace(to_replace=seasons_dict, inplace=True)
        wtl = temperature_limit.winter
        stl = temperature_limit.summer
        days.loc[days["TAMB"] < wtl, "season_t"] = "W"
        days.loc[days["TAMB"] >= wtl, "season_t"] = "U"
        days.loc[days["TAMB"] > stl, "season_t"] = "S"
        days.pop("TAMB")

        if self._set_season == "temperature":
            days["season"] = days.pop("season_t")
            days.pop("season_fix")
        else:
            days["season"] = days.pop("season_fix")
            days.pop("season_t")

        # 2. Set second letter of type days: Day of the week
        days.loc[days["weekday"] == 7, "day_of_week"] = "S"
        days.loc[days["weekday"] < 7, "day_of_week"] = "W"
        days.pop("weekday")

        # 3. Set third letter of type days: Cloud coverage
        days.loc[days["season"] == "S", "cloud_category"] = "X"

        # Combine the three letters in one column
        days["day_types"] = (
            days["season"] + days["day_of_week"] + days["cloud_category"]
        )
        days = days.drop(columns=["season", "day_of_week", "cloud_category"])
        return days

    def _load_profile_factors(self, tl):
        """Run VDI 4655 - Step 2.

        Match 'typtag' keys and reference load profile factors for each
        timestep (for each 'typtag' key, one load profile is defined by
        VDI 4655)
        """
        # Load data of typical days from VDI
        fn_typtage = os.path.join(
            os.path.dirname(__file__), "vdi_data", "VDI_4655_Typtage.csv"
        )
        typtage_df = pd.read_csv(fn_typtage, index_col=[0, 1])

        # Extract list of house types (expect: EFH, MFH)
        house_types = list(typtage_df.index.get_level_values(0).unique())

        # Convert time into datetime format
        typtage_df["time"] = pd.to_datetime(
            typtage_df.pop("Zeit"), format="%H:%M:%S"
        )

        # Calculate minutes of the day for every time step
        typtage_df["minute_of_day"] = (
            pd.to_timedelta(
                typtage_df["time"]
                - pd.Series(
                    index=typtage_df.index, data=typtage_df["time"].iloc[0]
                )
            )
            .dt.total_seconds()
            .div(60)
            .astype(int)
        )

        # Add columns to merge with (house types and day_types)
        typtage_df["ht"] = typtage_df.index.get_level_values(0)
        typtage_df["day_types"] = typtage_df.index.get_level_values(1)

        # Create a table for every minute of the year
        minute_table = pd.DataFrame(
            index=pd.date_range(
                f"1/1/{self._year}", periods=self.hoy * 60, freq="Min"
            )
        )

        # Set reference time (first hour of the day) to calculate minutes of
        # the day.
        self.type_days[tl]["ref_dt"] = self.type_days[tl].index

        # Fill data into the large table with minute index
        self.type_days[tl] = pd.concat(
            [self.type_days[tl], minute_table],
            axis=1,
            sort=True,
        ).ffill()

        # Add columns to merge with (house types, minute of day and day_types)
        self.type_days[tl]["datetime"] = self.type_days[tl].index
        self.type_days[tl]["minute_of_day"] = (
            pd.to_timedelta(
                self.type_days[tl].pop("datetime")
                - pd.Series(
                    index=self.type_days[tl].index,
                    data=self.type_days[tl].pop("ref_dt"),
                )
            )
            .dt.total_seconds()
            .div(60)
            .astype(int)
        )

        # Merge table for both house type to get the value of every minute of
        # the typical days for every minute of the year.
        house_profiles = {}
        for house_type in house_types:
            self.type_days[tl]["ht"] = house_type
            house_profiles[house_type] = (
                self.type_days[tl]
                .merge(
                    typtage_df,
                    how="left",
                    left_on=["day_types", "minute_of_day", "ht"],
                    right_on=["day_types", "minute_of_day", "ht"],
                )
                .sort_index()
            )

        # Combine the table of both house type
        load_profile = (
            pd.concat(
                [
                    house_profiles["EFH"][
                        ["F_el_n_TT", "F_Heiz_n_TT", "F_TWW_n_TT"]
                    ],
                    house_profiles["MFH"][
                        ["F_el_n_TT", "F_Heiz_n_TT", "F_TWW_n_TT"]
                    ],
                ],
                keys=["EFH", "MFH"],
                axis=1,
            )
            # .swaplevel(0, 1, axis=1)
            .sort_index(axis=1)
        )

        # Set time index to make it possible to reshape the table
        load_profile = load_profile.set_index(minute_table.index)
        load_profile.ffill(inplace=True)
        load_profile.loc[:, ("MFH", slice(None))] *= 1 / 15
        return load_profile

    def add_houses(self, houses):
        """Add houses to the region object.

        Parameters
        ----------
        houses : list
            A list of dictionaries that describes the houses.

            Required parameters for each house:

            * ``name``: Unique identifier for the house
            * ``house_type``: Either "EFH" (single-family) or
              "MFH" (multi-family)
            * ``N_Pers``: Number of persons, up to 12 (relevant for EFH)
            * ``N_WE``: Number of apartments, up to 40 (relevant for MFH)
            * ``Q_Heiz_a``: Annual heating demand in kWh
            * ``Q_TWW_a``: Annual hot water demand in kWh
            * ``W_a``: Annual electricity demand in kWh

            Optional:

            * ``summer_temperature_limit``: Temperature threshold for
              summer season (default: 15°C)
            * ``winter_temperature_limit``: Temperature threshold for
              winter season (default: 5°C)

        """
        houses_wrong = r"\n".join(
            [str(h) for h in houses if h["house_type"] not in ["EFH", "MFH"]]
        )

        if len(houses_wrong) > 0:
            msg = (
                f"The following house types are not supported:\n{houses_wrong}"
            )
            raise ValueError(msg)

        self.houses.extend(houses)
        self.temperature_limits = self._get_temperature_level_combinations()

    def get_daily_energy_demand_houses(self, tl):
        """Determine the houses' energy demand values for each 'typtag'.

        .. note::
            "The factors ``F_el_TT`` and ``F_TWW_TT`` are negative in some
            cases as they represent a variation from a one-year average. The
            values for the daily demand for electrical energy, ``W_TT``, and
            DHW energy, ``Q_TWW_TT``, usually remain positive. It is only in
            individual cases that the calculation for the typical-day category
            ``SWX`` can yield a negative value of the DHW demand. In that case,
            assume ``F_TWW_SWX`` = 0." (VDI 4655, page 16)

            This occurs when ``N_Pers`` or ``N_WE`` are larger than their
            allowed maximum of 12 persons (for single-family houses) and 40
            apartments (for multi-family houses).

        """
        if tl not in self.type_days:
            self.type_days[tl] = self._get_typical_days(self._holidays, tl)
        # typtage_combinations = settings["typtage_combinations"]
        # houses_list = settings["houses_list_VDI"]

        if self.zero_summer_heat_demand:
            # Reduze the value of 'F_Heiz_TT' to zero.
            # For modern houses, this eliminates the heat demand in summer
            self.energy_factors.loc[
                (slice(None), "F_Heiz_TT"), ("SWX", "SSX")
            ] = 0

        # Create a new DataFrame with multiindex.
        # It has two levels of columns: houses and energy
        # The DataFrame stores the individual energy demands for each house in
        # each time step
        energy_demands_types = ["Q_Heiz_TT", "W_TT", "Q_TWW_TT"]
        house_names = [n["name"] for n in self.houses]
        iterables = [house_names, energy_demands_types]
        multiindex = pd.MultiIndex.from_product(
            iterables, names=["house", "energy"]
        )
        typtage_combinations = self.type_days[tl]["day_types"].unique()

        daily_energy_demand_houses = pd.DataFrame(
            index=multiindex, columns=typtage_combinations, dtype="float"
        )

        # Fill the DataFrame daily_energy_demand_houses
        for house in self.houses:
            house_type = house["house_type"]
            n_pers = house["N_Pers"]
            n_we = house["N_WE"]

            # Get yearly energy demands
            q_heiz_a = house["Q_Heiz_a"]
            w_a = house["W_a"]
            q_tww_a = house["Q_TWW_a"]

            # (6.4) Do calculations according to VDI 4655 for each 'typtag'
            for typtag in typtage_combinations:
                f_heiz_tt = self.energy_factors.loc[house_type, "F_Heiz_TT"][
                    typtag
                ]
                f_el_tt = self.energy_factors.loc[house_type, "F_el_TT"][
                    typtag
                ]
                f_tww_tt = self.energy_factors.loc[house_type, "F_TWW_TT"][
                    typtag
                ]

                q_heiz_tt = q_heiz_a * f_heiz_tt

                if house_type == "EFH":
                    n_pers_we = n_pers
                else:
                    n_pers_we = n_we

                w_tt = w_a * (1.0 / 365.0 + n_pers_we * f_el_tt)
                q_tww_tt = q_tww_a * (1.0 / 365.0 + n_pers_we * f_tww_tt)

                if w_tt < 0:
                    msg = (
                        f"Warning:     W_TT for {house['name']} and"
                        f"{typtag} was negative, see VDI 4655 page 16"
                    )
                    warnings.warn(msg, UserWarning)
                    w_tt = w_a * (1.0 / 365.0 + n_pers_we * 0)

                if q_tww_tt < 0:
                    msg = (
                        f"Warning: Q_TWW_TT for {house['name']}"
                        f" and {typtag} was negative, see VDI 4655 page 16"
                    )
                    warnings.warn(msg, UserWarning)
                    q_tww_tt = q_tww_a * (1.0 / 365.0 + n_pers_we * 0)

                # Write values into DataFrame
                daily_energy_demand_houses.loc[
                    (house["name"], "Q_Heiz_TT"), typtag
                ] = q_heiz_tt
                daily_energy_demand_houses.loc[
                    (house["name"], "W_TT"), typtag
                ] = w_tt
                daily_energy_demand_houses.loc[
                    (house["name"], "Q_TWW_TT"), typtag
                ] = q_tww_tt

        return daily_energy_demand_houses

    def get_load_curve_houses(self):
        """Generate time series of energy demand values for all houses.

        This method calculates the energy demands heating, hot water,
        and electricity for each house in the region based on the VDI 4655
        typical day profiles. The calculation uses daily energy demands and
        typical load profiles, which are combined to create a full year
        time series for each house and energy type.

        The resulting time series are normalized to match the annual energy
        demands specified in the house parameters (Q_Heiz_a, Q_TWW_a, W_a).

        Returns
        -------
        pandas.DataFrame
            MultiIndex DataFrame with the following structure:

            - Index: DatetimeIndex with the time steps

            - Columns: MultiIndex with levels

              - name: House identifier
              - house_type: Either "EFH" or "MFH"
              - energy: Energy type ("Q_Heiz_TT", "Q_TWW_TT", or "W_TT")

            - Values: Energy demand in kWh per time step

        """
        daily_energy_demand_houses = {}
        for temp_limit in self.temperature_limits:
            daily_energy_demand_houses[temp_limit] = (
                self.get_daily_energy_demand_houses(temp_limit)
            )
            if temp_limit not in self._load_profiles:
                self._load_profiles[temp_limit] = self._load_profile_factors(
                    temp_limit
                )
            if self._resample_rule is not None:
                self._resample_profiles(self._resample_rule, temp_limit)

        house_profiles = {}

        for house in self.houses:
            t_limit = namedtuple("temperature_limit", "summer winter")
            tl = t_limit(
                summer=house.get("summer_temperature_limit", 15),
                winter=house.get("winter_temperature_limit", 5),
            )
            df_typ = (
                self.type_days[tl]
                .merge(
                    daily_energy_demand_houses[tl].T[house["name"]],
                    left_on="day_types",
                    right_index=True,
                )
                .sort_index()
            )
            df_typ = df_typ.drop(columns=["day_types", "minute_of_day", "ht"])

            load_profile_df = self._load_profiles[tl].rename(
                columns={
                    "F_Heiz_n_TT": "Q_Heiz_TT",
                    "F_el_n_TT": "W_TT",
                    "F_TWW_n_TT": "Q_TWW_TT",
                }
            )

            load_curve_house = df_typ.mul(load_profile_df[house["house_type"]])

            # The typical day calculation inherently does not add up to the
            # desired total energy demand of the full year. Here we fix that:
            for column in load_curve_house.columns:
                q_a = house[column.replace("TT", "a")]
                sum_ = load_curve_house[column].sum()
                if sum_ > 0:  # Would produce NaN otherwise
                    load_curve_house[column] = (
                        load_curve_house[column] / sum_ * q_a
                    )
            load_curve_house.columns = pd.MultiIndex.from_product(
                [
                    [house["house_type"]],
                    load_curve_house.columns,
                ]
            )
            house_profiles[house["name"]] = load_curve_house
        df = pd.concat(
            house_profiles.values(), keys=house_profiles.keys(), axis=1
        )

        df.columns = df.columns.set_names(["name", "house_type", "energy"])
        return df
