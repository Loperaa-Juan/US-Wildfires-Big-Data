import pandas as pd

from us_wildfires_big_data.etl.transform import hhmm_to_hour, julian_to_date


def test_julian_to_date_returns_midnight_of_that_day():
    # 2453403.5 is the julian day of 2005-02-02
    assert julian_to_date(pd.Series([2453403.5])).tolist() == [pd.Timestamp("2005-02-02")]


def test_hhmm_to_hour_keeps_unknown_times_null():
    hours = hhmm_to_hour(pd.Series(["1300", "0000", "2359", None]))

    assert hours.tolist() == [13, 0, 23, pd.NA]
    assert hours.dtype == "Int64"
