from typing import Dict
from tcas.models import Aircraft

def head_on_low_sep() -> Dict[str, Aircraft]:
    # Two aircraft head-on at ~250 kt each, small vertical sep
    return {
        "AAL101": Aircraft("AAL101", pos_m=(-12000, 0), vel_mps=(130, 0), alt_ft=10000, climb_fps=0),
        "UAL202": Aircraft("UAL202", pos_m=( 12000, 0), vel_mps=(-130, 0), alt_ft=10550, climb_fps=0),
    }

def crossing() -> Dict[str, Aircraft]:
    return {
        "DAL305": Aircraft("DAL305", pos_m=(-8000, -6000), vel_mps=(140,  60), alt_ft=12000, climb_fps=5),
        "JBU707": Aircraft("JBU707", pos_m=(-8000,  6000), vel_mps=(140, -60), alt_ft=11800, climb_fps=-5),
    }

def overtake_three() -> Dict[str, Aircraft]:
    return {
        "WJA010": Aircraft("WJA010", pos_m=(-10000,0), vel_mps=(170, 0), alt_ft=11000, climb_fps=0),
        "ACA415": Aircraft("ACA415", pos_m=( -2000,0), vel_mps=(150, 0), alt_ft=10950, climb_fps=0),
        "RYR900": Aircraft("RYR900", pos_m=(  7000,0), vel_mps=(130, 0), alt_ft=11100, climb_fps=0),
    }

SCENARIOS = {
    "1": head_on_low_sep,
    "2": crossing,
    "3": overtake_three,
}
