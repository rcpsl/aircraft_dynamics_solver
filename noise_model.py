import math


def combined_db(raw_db, n_total, db_per_craft):
    """
    Calculate the total dB level at a station given an ambient baseline,
    a number of aircraft present, and the noise level each aircraft produces.

    raw_db      : ambient / zone-baseline dB level (e.g. 52.0 for Mixed-Use Corridor)
    n_total     : total number of aircraft at the station at a given timestep
    db_per_craft: dB level produced by a single aircraft at reference distance

    Formula: 10 * log10( 10^(raw_db/10) + n_total * 10^(db_per_craft/10) )
    When n_total == 0 the aircraft term vanishes and the result equals raw_db.

    Returns: combined dB level (float)
    """
    if n_total == 0:
        return float(raw_db)
    ambient_power  = 10 ** (raw_db      / 10)
    aircraft_power = n_total * (10 ** (db_per_craft / 10))
    return 10 * math.log10(ambient_power + aircraft_power)
