# -*- coding: utf-8 -*-

"""
Verifying the building model using data from the Tabula Project.

https://www.episcope.eu
https://webtool.building-typology.eu

Autor: Uwe Krien <uwe.krien@ifam.fraunhofer.de>
Lizenz: MIT
"""

from pathlib import Path

import pandas as pd

from oemof.demand.tabula import single_zone_building as szb

url = "https://www.episcope.eu/downloads/public/calc/tabula-calculator.xlsx"

# Adapt the following path accordingly to the
file_orig = Path(r"C:\Users", "name", "Downloads", "tabula-calculator.xlsx")
# file_orig = Path("/home", "name", "Downloads", "tabula-calculator.xlsx")
file_processed = Path(Path.home(), "tabula-calculator_de_processed.csv")


def process_data_file(in_file, out_file):
    if not file_orig.exists():
        msg = (
            f"File {in_file} not found. Please download it from {url} and "
            f"adapt the Path of 'file_orig' in the example code."
        )
        raise FileNotFoundError(msg)

    buildings_tabula_xlsx = pd.read_excel(
        in_file,
        index_col=[0],
        header=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        sheet_name="Calc.Set.Building",
    ).droplevel([1, 2, 3, 4, 5, 6, 7, 8, 9], axis=1)

    # Filter buildings from Germany
    buildings_tabula_xlsx_de = buildings_tabula_xlsx.loc[
        buildings_tabula_xlsx.index.str.contains("DE.N|DE.East")
        & buildings_tabula_xlsx.index.str.contains("ReEx")
    ]
    # Store as csv file
    buildings_tabula_xlsx_de.to_csv(out_file)


if not file_processed.exists():
    process_data_file(file_orig, file_processed)

# Read csv data file from tabula
buildings_tabula = pd.read_csv(
    Path(Path.home(), "tabula-calculator_de_processed.csv"),
    index_col=[0],
    header=[0],
)

# Create an area object for all tabula buildings of Germany
area_cols = {
    c: c.replace("A_Calc_", "")
    for c in buildings_tabula.columns
    if "A_Calc_" in c and c[-1] in ["1", "2", "3"]
}
areas = szb.EnvelopeParameter.from_dataframe(
    buildings_tabula[area_cols.keys()].rename(columns=area_cols)
)

print(
    "\nYou can add correction factors for all elements, e.g. for wall parts "
    "in contact with the ground.\nIf you set 'add_missing' to True, all "
    "values will be set to 1, unless you specify a different value.\nThe "
    "safest option is to add a value for all building parts.:\n"
    + ", ".join(areas.flat_df.columns)
)
areas.add_correction_factors(
    {"Floor_1": 0.5, "Floor_2": 0.5, "Wall_2": 0.5},
    add_missing=True,
)

# Create an u_value object for all tabula buildings of Germany
u_value_cols = {
    c: c.replace("U_Actual_", "")
    for c in buildings_tabula.columns
    if "U_Actual_" in c and c[-1] in ["1", "2", "3"]
}
u_values = szb.EnvelopeParameter.from_dataframe(
    buildings_tabula[u_value_cols.keys()].rename(columns=u_value_cols)
)

solar_gain_reduction = (
    buildings_tabula["g_gl_n"]  # transmission factor
    * buildings_tabula["F_sh_vert"]  # reduction factor external shading
    * (1 - buildings_tabula["F_f"])  # frame area fraction of window
    # reduction factor, considering radiation non-perpendicular to the glazing
    * buildings_tabula["F_w"]
)

# The window orientation factor  can be used if there are no information about
# the orientation of the windows. This factor is not used in the tabula
# calculation. In tabula the orientation is used. Therefore, the factor is a
# helpful to estimate the orientation.
window_orientation_factor = buildings_tabula["q_sol"] / (
    areas.window.sum(axis=1)  # area of all windows
    * buildings_tabula["g_gl_n"]  # transmission factor
    * buildings_tabula["F_sh_vert"]  # reduction factor external shading
    * (1 - buildings_tabula["F_f"])  # frame area fraction of window
    # reduction factor, considering radiation non-perpendicular to the glazing
    * buildings_tabula["F_w"]
    * buildings_tabula["I_Sol_Hor"]  # irradiation at heating days on horiz.
    / buildings_tabula["A_C_Ref"]  # conditioned area
)

# Add the basic data of the buildings
bt = szb.BuildingTable(
    area=areas,
    floor_height=buildings_tabula["h_room"],
    conditioned_floor_area=buildings_tabula["A_C_Ref"],
    window_orientation_factor=window_orientation_factor,
)

# Add heat specific data that might vary due to the quality of the insulation
results = bt.specific_annual_heating_demand(
    u_value=u_values,
    thermal_bridges_factor=buildings_tabula["delta_U_ThermalBridging"],
    ventilation_rate=buildings_tabula["n_air_use"]
    + buildings_tabula["n_air_infiltration"],
    gain_utilisation_factor=buildings_tabula["eta_h_gn"],
    transmittance_windows=buildings_tabula["g_gl_n"],
    heating_degree_days=buildings_tabula["Sum_DeltaT_for_HeatingDays"]
    * buildings_tabula["F_red_temp"],
    heating_days=buildings_tabula["HeatingDays"],
    irradiation_heating_season=buildings_tabula["I_Sol_Hor"],
)

# Compare the calculated results with the tabula results.
# All value should be equal because the single-zone-model uses the same
# equations as tabula does. Using the same input data should end in the same
# results
tabula_results = buildings_tabula["q_h_nd"]
tabula_results.name = "tabula"

calculated_results = pd.DataFrame(results.sum(axis=1), columns=["calculated"])

df = pd.concat([tabula_results, calculated_results["calculated"]], axis=1)
print(df)
print(df.sum())

calculated_results["status"] = calculated_results.index.str[-3:].astype(int)
calculated_results["tabula_id"] = calculated_results.index.str[:-4]

tab = calculated_results.set_index(["tabula_id", "status"]).squeeze().unstack()
print(tab)
