Changelog
=========

v0.2.3 (YYYY-MM-DD)
+++++++++++++++++++++++++

New features
############

Bug fixes
#########
*   Implement default temperature limits for VDI 4655 calculation to make
    ``summer_temperature_limit`` and ``winter_temperature_limit`` optional
*   Fix leap year handling in VDI 4655 profiles

Other changes
#############

* Documentation improvements.
* First version to be named oemof.demand.
* Warn when a profile is created without ``holidays``, because public
  holidays are then treated as the weekday they fall on. Pass
  ``holidays=[]`` to model a period without public holidays explicitly.
* Stop using pandas API deprecated in pandas 3.1 (``DatetimeIndex.weekday``
  and ``inplace`` in ``drop``, ``rename``, ``set_index`` and ``sort_index``).


v0.2.2 (2025-04-09)
+++++++++++++++++++++++++

*   Added Electricity standard load profiles as released by the BDEW in 2025.
*   Added VDI profile based on LPagg


v0.2.1 (2024-08-06)
+++++++++++++++++++++++++

New features
############
*   Allow to have holidays in industrial profile

Bug fixes
#########
*   simple_profile from IndustrialLoadProfile behaved differently in version
    0.2.0 compared to 0.1.9 due to pandas masking functions. We are now back
    to the old (design) values.


v0.2.0 (2024-06-27)
+++++++++++++++++++++++++

Bug fixes
#########
*   Raise error for non supported shlp_type
	in non-commercial buildings

Other changes
#############
*   Adhere to packaging standards
* 	Raise errors in sigmoid parameter queries


v0.1.9 (2023-03-18)
+++++++++++++++++++++++++

*   Calculation of BDEW profiles was improved



v0.1.8 (2021-01-27)
+++++++++++++++++++++++++

Bug fixes
#########
*   FutureWarning for "dyn_function_h0" was raised instead of printed



v0.1.7 (2021-01-27)
+++++++++++++++++++++++++

New features
############
*   Add dynamic h0 profile calculation
    (The implementation is not optimised for performance.
    Thus, it is not used by default.)

Bug fixes
#########
*   Fix improper use of pandas.dataframe.merge
    (oemof-demand will now work with pandas>=1.2)

Other changes
#############
*   Update deprecated pd.datetime to datetime.datetime
*   Add (integration) tests and coverage as CI
*   Split BDEW profile generation into submodules



v0.1.6 (2019-01-30)
+++++++++++++++++++++++++

General
#######

* Update requirements
* Fix typos



v0.1.5 (2018-09-05)
+++++++++++++++++++++++++

New features
############

* Add function `get_normalized_bdew_profile(self)` to get a normalised profile. You could also use an annual_demand of one to get the same results.

Bug fixes
#########

* Fix y-label of the heat example plot.

Other changes
#############

* Make matplotlib optional in examples.



v0.1.4 (2018-05-30)
+++++++++++++++++++++++++

Code
####

 * fix temperature bug
 * fix Code style

Documentation
#############

 * Documentation improvements.



v0.1.1 (2016-11-30)
+++++++++++++++++++++++++

New features
############
* Examples callable by command-line script

Bug fixes
#########
* Path specs when installed via pip

Other changes
#############
* Fix versioning



0.1.0 (2016-10-04)
+++++++++++++++++++++++++

New features
############
* Implementation of BDEW synthetic load profiles
* Synthetic load profiles for heating sector
* Self-made industry demand profile similar to BDEW profiles
