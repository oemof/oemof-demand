# -*- coding: utf-8 -*-

"""
The following example shows how to calculate a large number of buildings.

Autor: Uwe Krien <uwe.krien@ifam.fraunhofer.de>
Lizenz: MIT
"""

from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt

from oemof.demand.tabula import single_zone_building as szb

# Read example data. This data can be used as a starting point for typical
# houses in Germany. See https://webtool.building-typology.eu for more details.
building_geometry = pd.read_csv(
    Path("data_building_geometry.csv"), header=[0, 1], index_col=[0]
)
buildings = pd.read_csv(
    Path("data_building_state.csv"), header=[0, 1], index_col=[0, 1]
)

# Add the area of the building parts for each building
areas = szb.EnvelopeParameter.from_dataframe(building_geometry["area of element"])
areas.add_correction_factors(
    {"Floor_1": 0.5, "Floor_2": 0.5, "Wall_2": 0.5}, add_missing=True
)

# Create an object for all houses.
bt = szb.BuildingTable(
    area=areas,
    floor_height=building_geometry["floor height", "building"],
    conditioned_floor_area=building_geometry["conditioned area", "building"],
    window_orientation_factor=building_geometry[
        "orientation factor", "window"
    ],
)


# Calculate the specific heat demand for all buildings and different energy
# performance levels (states) of the buildings.
results = {}
for state in [1, 2, 3]:
    building_state = buildings.loc[state]
    u_values = szb.EnvelopeParameter.from_dataframe(buildings["u_values"].loc[state])
    results[state] = bt.specific_annual_heating_demand(
        u_value=u_values,
        thermal_bridges_factor=building_state[
            "thermal bridges factor", "building"
        ],
        ventilation_rate=building_state["ventilation rate", "building"],
        gain_utilisation_factor=building_state[
            "gain utilisation factor", "building"
        ],
        transmittance_windows=building_state["transmission factor", "window"],
        heating_degree_days=building_state["heating degree days", "building"]
        * building_state["temperature reduction factor", "building"],
        heating_days=building_state["heating days", "building"],
        irradiation_heating_season=building_state[
            "irradiation heating season", "building"
        ],
    )
results_all = pd.concat(results.values(), keys=results.keys(), axis=1)

# Show results of one performance level e.g. 1
results_state = results[1]

# Assign the elements to their main groups.
elements = ["door", "floor", "wall", "window", "roof"]
renamer = {c: c for c in results_state.columns}
for element in elements:
    renamer.update(
        {c: element for c in results_state.columns if element in c.lower()}
    )
results_grp = results_state.T.groupby(renamer).sum().T

# Show all buildings for the performance level selected above.
print(results_state.sum(axis=1))
results_grp.plot(kind="bar", stacked=True)
plt.show()

# Show one building for all 3 performance levels.
results_all.loc[1].unstack().plot(kind="bar", stacked=True)
plt.show()
