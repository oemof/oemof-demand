"""Tools needed by the main classes."""

import warnings

import pandas as pd


def add_weekdays2df(
    time_df: pd.DataFrame,
    holidays: dict | list | None = None,
    holiday_is_sunday: bool = False,
):
    r"""Giving back a DataFrame containing weekdays and optionally holidays for
     the given year.

    Parameters
    ----------
    time_df : pandas DataFrame
        DataFrame to which the weekdays should be added

    Optional Parameters
    -------------------
    holidays : list or dict containg dates of holidays (see set_holidays_in_df)

    holiday_is_sunday : boolean
        If set to True, all holidays (0) will be set to sundays (7).

    Returns
    -------
    pandas.DataFrame : DataFrame with weekdays

    Notes
    -----
    Using Pandas > 0.16

    """
    time_df["weekday"] = time_df.index.day_of_week + 1
    time_df["date"] = time_df.index.date

    set_holidays_in_df(time_df, holidays)

    if holiday_is_sunday:
        time_df.weekday = time_df.weekday.mask(
            cond=time_df.weekday == 0, other=7
        )

    return time_df


def set_holidays_in_df(
    time_df: pd.DataFrame, holidays: dict | list | None
) -> None:
    r"""Giving back a DataFrame containing weekdays and optionally holidays for
     the given year.

    Parameters
    ----------
    time_df : pandas DataFrame
        DataFrame in which the "weekday" (1..7)
        should replaced by 0 for holidays

    holidays : list or dict containg dates of holidays. If a dict is chosen,
        the key should identify the date, dict values are ignored. If None,
        a warning is issued and no holidays are set; pass an empty list to
        model a period without public holidays without the warning.

    Returns
    -------
    pandas.DataFrame : DataFrame with weekdays
    """
    if holidays is None:
        warnings.warn(
            "No holidays given, so public holidays are treated as the weekday"
            " they fall on. Pass `holidays` as a list or dict of dates (for"
            " example from the `holidays` or `workalendar` package) to model"
            " them, or `holidays=[]` to silence this warning.",
            UserWarning,
            stacklevel=2,
        )
        return None

    # Set weekday to Holiday (0) for all holidays
    if len(holidays) > 0:
        if isinstance(holidays, dict):
            holidays = list(holidays.keys())
        time_df["weekday"] = time_df["weekday"].mask(
            cond=pd.to_datetime(time_df.index.date).isin(
                pd.to_datetime(holidays)
            ),
            other=0,
        )

    return None
