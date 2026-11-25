import datetime

import pandas as pd
import pytest

from oemof.demand import bdew


class TestElecSLP:
    @classmethod
    def setup_class(cls):
        cls.slp = bdew.ElecSlp(2010)
        cls.dt_index = pd.date_range(
            datetime.datetime(2010, 1, 1, 0), periods=8760 * 4, freq="15Min"
        )
        cls.slp_types = [
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
        cls.holidays = {
            datetime.date(2010, 5, 24): "Whit Monday",
            datetime.date(2010, 4, 5): "Easter Monday",
            datetime.date(2010, 5, 13): "Ascension Thursday",
            datetime.date(2010, 1, 1): "New year",
            datetime.date(2010, 10, 3): "Day of German Unity",
            datetime.date(2010, 12, 25): "Christmas Day",
            datetime.date(2010, 5, 1): "Labour Day",
            datetime.date(2010, 4, 2): "Good Friday",
            datetime.date(2010, 12, 26): "Second Christmas Day",
        }

    def test_elec_slp_year(self):
        assert self.slp.year == 2010

    def test_columns_of_frame(self):
        assert sorted(self.slp.slp_frame.columns) == [
            "g0",
            "g1",
            "g2",
            "g3",
            "g4",
            "g5",
            "g6",
            "h0",
            "h0_dyn",
            "l0",
            "l1",
            "l2",
        ]

    def test_index_of_frame(self):
        assert isinstance(self.slp.slp_frame.index, pd.DatetimeIndex)
        assert len(self.slp.slp_frame.index) == 8760 * 4

    def test_index_for_leap_year(self):
        assert len(bdew.ElecSlp(2012).slp_frame.index) == 8760 * 4 + 24 * 4

    def test_frame_without_holidays(self):
        with pytest.warns(UserWarning, match="No holidays given"):
            my_frame = self.slp.create_bdew_load_profiles(
                self.dt_index, self.slp_types, holidays=None
            )
        my_frame = pd.concat(
            [my_frame, self.slp.create_dynamic_h0_profile()], axis=1
        )
        pd.testing.assert_frame_equal(self.slp.slp_frame, my_frame)

    def test_frame_with_holidays(self):
        my_frame = self.slp.create_bdew_load_profiles(
            self.dt_index, self.slp_types, holidays=self.holidays
        )
        with pytest.raises(AssertionError):
            pd.testing.assert_frame_equal(self.slp.slp_frame, my_frame)

        # with holidays
        assert (
            round(my_frame.loc[datetime.datetime(2010, 5, 24, 12, 0), "h0"], 6)
            == 0.000054
        )
        # without holidays
        assert (
            round(
                self.slp.slp_frame.loc[
                    datetime.datetime(2010, 5, 24, 12, 0), "h0"
                ],
                6,
            )
            == 0.000038
        )

    def test_deprecated_method(self):
        with pytest.warns(FutureWarning) as record:
            self.slp.get_profile(ann_el_demand_per_sector={"h0": 5000})
        assert len(record) == 1
        assert "This method is deprecated" in record[0].message.args[0]


def test_changed_seasons():
    """Test changing the seasons."""
    alt_seasons = {
        "summer1": [5, 2, 9, 14],  # summer: 2.05. to 14.09
        "transition1": [3, 21, 5, 1],  # transition1 :21.03. to 1.05.
    }
    slp1 = bdew.ElecSlp(2010)
    slp2 = bdew.ElecSlp(2010, seasons=alt_seasons)
    # 6th-7th May, 2010
    assert slp1.get_profiles("g0").index[12000] == datetime.datetime(
        2010, 5, 6, 0, 0
    )
    assert slp1.get_profiles("g0").index[12096] == datetime.datetime(
        2010, 5, 7, 0, 0
    )
    # transition1 in a normal slp
    assert (
        round(slp1.get_profiles("g0").iloc[12000:12096].sum().iloc[0], 5)
        == 0.00300
    )
    # summer1 in a changed time scale
    assert (
        round(slp2.get_profiles("g0").iloc[12000:12096].sum().iloc[0], 5)
        == 0.00612
    )


def test_slp25():
    holiday_dict = {
        datetime.date(2010, 1, 1): "New year",
        datetime.date(2010, 4, 2): "Good Friday",
        datetime.date(2010, 4, 5): "Easter Monday",
        datetime.date(2010, 5, 1): "Labour Day",
        datetime.date(2010, 5, 13): "Ascension Thursday",
        datetime.date(2010, 5, 24): "Whit Monday",
        datetime.date(2010, 10, 3): "Day of German Unity",
        datetime.date(2010, 12, 25): "Christmas Day",
        datetime.date(2010, 12, 26): "Second Christmas Day",
    }

    holiday_list = list(holiday_dict.keys())

    index01m = pd.date_range(  # 1 minute time steps
        start="2010-01-01 00:00",
        end="2010-12-31 23:45",
        freq="1min",
    )

    index15m = pd.date_range(  # 15 minute time steps
        start="2010-01-01 00:00",
        end="2010-12-31 23:45",
        freq="15min",
    )

    index60m = pd.date_range(  # 60 minute time steps
        start="2010-01-01 00:00",
        end="2010-12-31 23:45",
        freq="60min",
    )

    index_2years = pd.date_range(  # 2010 and 2011
        start="2010-01-01 00:00",
        end="2011-12-31 23:45",
        freq="15min",
    )

    index_shifted_year = pd.date_range(  # 12 month starting June 2010
        start="2010-06-01 00:00",
        end="2011-05-31 23:45",
        freq="15min",
    )

    with pytest.raises(NotImplementedError):
        _ = bdew._profiles25.BDEW25Profile(index15m)

    with pytest.raises(NotImplementedError):
        _ = bdew._profiles25.DynamicBDEW25Profile(index15m)

    for slp_type in [bdew.G25, bdew.H25, bdew.L25, bdew.P25, bdew.S25]:
        # We allow 1.0 % tollerenace (with holidays)
        slp_profile = slp_type(index15m, holidays=holiday_dict)
        assert slp_profile.sum() / 4 == pytest.approx(1e6, rel=0.01)

        # SLP of a shorter index is just the excerpt of the original SLP
        short_slp = slp_type(index15m[5:1000], holidays=holiday_dict)
        assert short_slp.equals(slp_profile[5:1000])

        # Higher resolution samples the same SLP, the integral is unchanged
        slp_resampled = slp_type(index01m, holidays=holiday_list)
        assert slp_resampled.sum() / 15 == pytest.approx(
            slp_profile.sum(), rel=0.0001
        )

        # Lower time resolution averages, so integral is unchanged
        slp_resampled = slp_type(index60m, holidays=holiday_dict)
        assert slp_resampled.sum() * 4 == pytest.approx(
            slp_profile.sum(), rel=0.0001
        )

        # We allow 2.5 % tollerenace (without holidays)
        slp_profile = slp_type(index15m)
        assert slp_profile.sum() / 4 == pytest.approx(1e6, rel=0.025)

        # We allow 2.5 % tollerenace (without holidays)
        slp_profile = slp_type(index_shifted_year)
        assert slp_profile.sum() / 4 == pytest.approx(1e6, rel=0.025)

        # We allow 2.5 % tollerenace (without holidays), two years
        slp_profile = slp_type(index_2years)
        assert slp_profile.sum() / 4 == pytest.approx(2e6, rel=0.025)


@pytest.mark.parametrize("start", ["2010-01-01 18:00", "2010-01-01 18:15"])
def test_slp25_hourly_profiles_average_each_full_interval(start):
    hourly_index = pd.date_range(start, periods=2, freq="h")
    quarter_hour_index = pd.date_range(start, periods=8, freq="15min")
    quarters = bdew.H25(quarter_hour_index, holidays=[])

    hourly = bdew.H25(hourly_index, holidays=[])

    pd.testing.assert_index_equal(hourly.index, hourly_index)
    assert hourly.tolist() == pytest.approx(
        [quarters.iloc[:4].mean(), quarters.iloc[4:].mean()]
    )


@pytest.mark.parametrize("start", ["2024-03-30 00:15", "2024-10-26 00:15"])
def test_slp25_daily_profiles_follow_timezone_aware_interval_edges(start):
    edges = pd.date_range(start, periods=3, freq="D", tz="Europe/Berlin")
    quarter_hour_index = pd.date_range(
        edges[0], edges[-1], freq="15min", inclusive="left"
    )
    quarters = bdew.G25(quarter_hour_index, holidays=[])

    daily = bdew.G25(edges[:-1], holidays=[])

    expected = [
        quarters[(quarters.index >= left) & (quarters.index < right)].mean()
        for left, right in zip(edges[:-1], edges[1:])
    ]
    pd.testing.assert_index_equal(daily.index, edges[:-1])
    assert daily.tolist() == pytest.approx(expected)
