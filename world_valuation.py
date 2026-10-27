"""Transparent fictional transfer values for PES Challenge (not market quotations).

Estimates are based only on sourced EA overall, age at the selected dataset
date, and position group. Unknown ratings or dates give no estimate.
Potential, contract, wages and transfer fees are deliberately NOT inferred.
All currency amounts in GBP, rounded for gameplay, with model version.
"""
from math import exp

MODEL_VERSION = "prototype-v1"
POSITION_FACTOR = {
    "GK":0.70,"CB":0.83,"LB":0.85,"RB":0.85,"LWB":0.87,"RWB":0.87,
    "CDM":0.94,"CM":1.00,"CAM":1.08,"LM":1.04,"RM":1.04,
    "LW":1.17,"RW":1.17,"CF":1.20,"ST":1.20,
    "DEF":0.86,"MID":1.02,"FWD":1.18,
}


def model_value(overall, age, position):
    """GBP game-world reference valuation; NOT an offered transfer price."""
    if overall is None or age is None or not isinstance(overall,int) or not 1<=overall<=99 or age<15 or age>45:
        return None
    # Steep ability curve differentiates top-flight from lower-league players.
    # Example 65-rated peak-age footballer roughly £0.95m before position factor.
    base=950_000*exp((overall-65)*0.135)
    if age<=20:
        factor=1.18
    elif age<=24:
        factor=1.28
    elif age<=28:
        factor=1.00
    elif age<=31:
        factor=0.72
    elif age<=34:
        factor=0.43
    else:
        factor=0.22
    raw=base*factor*POSITION_FACTOR.get((position or "").upper(),1.0)
    # Avoid false precision and avoid simulated negative/zero valuations.
    nearest=25_000 if raw < 5_000_000 else 100_000
    return max(nearest,round(raw/nearest)*nearest)


FC27_GAME_VALUE_VERSION="fc27-source-wage-and-ability-calibration-v1"

def fc27_game_reference_value(*,baseline,overall,weekly_wage=None):
    """Modelled 2026/27 GAME-market reference, not a real transfer fee.

    The previous prototype v1 made an established 84 OVR international
    available for roughly £10-15m. A stronger high-ability curve and the
    actual source-game weekly wage provide a more meaningful starting
    reference. No market prices, external rumours or potential are invented.
    Older editions retain precisely their original v1 valuations.
    """
    if (type(baseline) is not int or baseline<=0 or
            type(overall) is not int or not 1<=overall<=99):
        raise ValueError("Rated and positive baseline required")
    if (weekly_wage is not None and
            (type(weekly_wage) is not int or weekly_wage<0)):
        raise ValueError("Source-game weekly wage must be nonnegative or unknown")
    strength_multiplier=min(3.6,1+max(0,overall-70)*.13)
    wage_yearly=52*(weekly_wage or 0)
    candidate=max(baseline*strength_multiplier+
                  min(baseline*.25,wage_yearly*.40),
                  wage_yearly*2.4)
    increment=100000 if candidate>=5_000_000 else 25000
    return min(350_000_000,max(increment,
        int((candidate+increment/2)//increment)*increment))

def display_gbp(amount):
    if amount is None:
        return "Not estimated"
    if amount>=1_000_000:
        return f"£{amount/1_000_000:.1f}m"
    return f"£{amount/1_000:.0f}k"


# Optional adjustment stage: this does not alter MODEL_VERSION/v1 baseline.
# A confirmed contract expiry is needed before using this function.
CONTRACT_MODEL_VERSION = "contract-adjustment-v1"


def contract_adjusted_value(baseline_value, months_remaining, *, confirmed=False):
    """Fictional negotiating reference; not a release fee or club asking price.

    If contract information is unknown/unverified, preserve the base value.
    Never infer duration from a player's age, rating or club.
    """
    if baseline_value is None:
        return None
    if not confirmed or months_remaining is None:
        return baseline_value
    if not isinstance(months_remaining, int) or months_remaining < 0:
        raise ValueError("months_remaining must be a nonnegative integer")
    # Smoothly taper prices as contracts near expiry, with a 30% floor.
    # Up to 24 months: 0 months -> 30%, 12 months -> 65%, >=24 -> 100%.
    multiplier = 0.30 + 0.70 * min(months_remaining, 24) / 24
    increment = 25_000 if baseline_value * multiplier < 5_000_000 else 100_000
    return max(increment, round(baseline_value * multiplier / increment) * increment)
