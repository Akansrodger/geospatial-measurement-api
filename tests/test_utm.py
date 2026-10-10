import pytest

from app.services.utm import select_utm_epsg


@pytest.mark.parametrize(
    "lon,lat,expected",
    [
        (3.005, 0.005, 32631),     # equator, zone 31 N
        (77.209, 28.614, 32643),   # Delhi
        (3.38, 6.52, 32631),       # Lagos
        (-74.0, 40.7, 32618),      # New York
        (151.2, -33.9, 32756),     # Sydney (south)
        (-180.0, 10.0, 32601),
        (180.0, 10.0, 32660),
        (0.0, 89.0, 32661),        # polar north
        (0.0, -85.0, 32761),       # polar south
    ],
)
def test_select_utm_epsg(lon, lat, expected):
    assert select_utm_epsg(lon, lat) == expected


@pytest.mark.parametrize("lon,lat", [(181, 0), (0, 91), (-200, 0)])
def test_out_of_range_raises(lon, lat):
    with pytest.raises(ValueError):
        select_utm_epsg(lon, lat)
