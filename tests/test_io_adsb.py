import csv

from tcas.io import load_adsb_with_ownship


def test_load_adsb_with_ownship(tmp_path):
    own_file = tmp_path / "own.csv"
    intr_dir = tmp_path / "scenario"
    intr_dir.mkdir()

    header = [
        "time_s", "aircraft_id", "df", "icao24", "mode",
        "altitude_ft", "vertical_rate_fpm", "on_ground",
        "tcas_equipped", "identity", "squawk",
        "range_nm", "bearing_deg", "range_rate_kt",
    ]

    # Ownship row
    with own_file.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow([0, "OWN1", 17, "ABC123", "S",
                    10000, 0, 0, 1, "OWNID", "7000",
                    0, 0, 0])

    # Intruder row (5 NM ahead, level, small closure)
    intr_file = intr_dir / "intr.csv"
    with intr_file.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow([0, "INTR1", 17, "DEF456", "S",
                    10000, 0, 0, 1, "INTRID", "7010",
                    5, 0, -250])

    traffic = load_adsb_with_ownship(str(own_file), str(intr_dir))

    assert "OWN1" in traffic
    assert "INTR1" in traffic
    own = traffic["OWN1"]
    intr = traffic["INTR1"]

    assert own.alt_ft == 10000
    assert intr.alt_ft == 10000
    # ownship should be at origin
    assert own.pos_m == (0.0, 0.0)
