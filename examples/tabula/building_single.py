# -*- coding: utf-8 -*-

"""
The following example shows how to calculate a single building.

You can find suitable input data on the Tabula website.
https://webtool.building-typology.eu

Autor: Uwe Krien <uwe.krien@ifam.fraunhofer.de>
Lizenz: MIT
"""

import numpy as np
from matplotlib import pyplot as plt

from oemof.demand.tabula import single_zone_building as szb

# Add the area of the building parts.
area = szb.EnvelopeParameter(
    window=389, floor=598.34, roof=598.34, wall=1673.73
)

# The floor area is reduced because less heat is lost through the ground.
area.add_correction_factors({"floor": 0.5}, add_missing=True)

# Create a building object
bt = szb.BuildingTable(
    area=area,
    floor_height=2.5,
    conditioned_floor_area=3107.5,
    window_orientation_factor=0.716846,
)

# Calculation of the specific heat demand for a defined renovation condition,
# a specific climate zone, and assumed heating behaviour.
u_values = szb.EnvelopeParameter(
    window=1.3, floor=0.235162, roof=0.160550, wall=0.195542
)

results = bt.specific_annual_heating_demand(
    u_value=u_values,
    heating_degree_days=3497,
    heating_days=222,
    thermal_bridges_factor=0.1,
    ventilation_rate=0.6,
    irradiation_heating_season=403,
    gain_utilisation_factor=0.958363,
    transmittance_windows=0.6,
)

# Show the results
print(results)
colors = [
    f"#{np.random.randint(0, 0xFFFFFF):06X}" for _ in range(len(results))
]
results.plot(kind="bar", color=colors)
plt.show()
