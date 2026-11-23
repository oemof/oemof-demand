# -*- coding: utf-8 -*-
"""
Read DWD TRY (test reference year) data.

SPDX-FileCopyrightText: Joris Zimmermann
SPDX-FileCopyrightText: Uwe Krien

SPDX-License-Identifier: MIT
"""

import os

import pandas as pd

try:
    import geopandas as gpd
    from shapely import Point
except ModuleNotFoundError:
    pass


def find_try_region(longitude, latitude):
    """
    Find the DWD TRY region by coordinates.

    .. note::
        - Latitude and longitude must be provided in the coordinate
          reference system ``EPSG:4326``.

        - The packages geopandas and shapely need to be installed to use this
          function.

    Parameters
    ----------
    longitude : float
    latitude : float

    Returns
    -------
    DWD TRY region number : int

    Raises
    ------
    ImportError
        If geopandas or shapely are not installed
    """
    fn_try_map = os.path.join(
        os.path.dirname(__file__), "resources_weather", "TRY_polygons.geojson"
    )
    try:
        try_map = gpd.read_file(fn_try_map)
        my_point = Point(longitude, latitude)
    except ModuleNotFoundError as e:
        raise ImportError(
            "geopandas and shapely are required for find_try_region(). "
            "Please install them with e.g.: pip install geopandas shapely"
        ) from e

    try_region = try_map.loc[try_map.contains(my_point), "TRY_code"].iloc[0]
    return try_region


def read_dwd_weather_file(weather_file_path):
    """Read and parse DWD test reference year (TRY) weather data files.

    This function reads TRY weather data files published by the German
    Weather Service (Deutscher Wetterdienst, DWD) and extracts
    temperature and cloud cover data.

    The 2016 DWD weather files can be obtained from:
    https://kunden.dwd.de/obt/ (registration required)

    Parameters
    ----------
    weather_file_path : str, optional
        Path to a TRY weather file. The file must follow the DWD format
        from 2010 or 2016. If None, a default file for the given try_region
        will be used.

    Returns
    -------
    pandas.DataFrame
        DataFrame with hourly weather data

    Raises
    ------
    TypeError
        If the weather file does not follow the expected DWD format
    FileNotFoundError
        If the weather file cannot be found

    """
    # The comments in DWD files before the header are not commented out.
    # Thus we have to search for the line with the header information:
    header_row = None
    with open(weather_file_path, "r") as rows:
        for number, row in enumerate(rows, 1):
            # The header is the row before the appearance of '***'
            if "***" in row:
                header_row = number - 1
                break

    # Plausibility check:
    if header_row is None:
        msg = (
            "Error: Header row not found in weather file. "
            'Is the data type "DWD" correct? Exiting...\nFile is: '
            + weather_file_path
        )
        raise TypeError(msg)

    # Read the file and store it in a DataFrame
    weather_data = pd.read_csv(
        weather_file_path,
        sep=r"\s+",
        skiprows=header_row - 1,
        index_col=["MM", "DD", "HH"],
        usecols=["MM", "DD", "HH", "t", "N"],
        comment="*",
    )

    # Rename the columns
    weather_data = weather_data.rename(
        columns={
            "t": "TAMB",
            "N": "CCOVER",
        },
    )

    return weather_data
