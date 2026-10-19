"""Versioned fictional player/agent choices, independent of source player consent.

Historical prestige is a PROVISIONAL gameplay input, never a claim that a
particular player or agent would actually make the assessed choice.
No wages, registrations, PES state or league results are mutated here.

A career's 92 historical scores must come from a frozen, explicit snapshot;
never silently load the latest calibration when evaluating an old career.
"""
from world_reputation_v2 import assess_player_interest

DECISION_VERSION = "player-decisions-v1"
LEGACY_VERSION = "legacy-sporting-v2"
SUPPORTED_VERSIONS = (LEGACY_VERSION, DECISION_VERSION)
# Squad hierarchy: Key Player > Regular Starter > Rotation > Fringe.
ROLES = ("unspecified","key_player","regular_starter","rotation","fringe")
SELECTABLE_ROLES = ("unspecified","key_player","regular_starter","rotation","fringe")
ROLE_LABELS = {
    "unspecified":"No guaranteed role",
    "key_player":"Key Player",
    "regular_starter":"Regular Starter",
    "rotation":"Rotation Player",
    "fringe":"Fringe Player",
    "none":"No additional guarantee",
    "unassessed":"Needs review",
    "unavailable":"Not available",
}
def canonical_role(role):
    return role
def role_satisfies(promise,requirement):
    promise,requirement=canonical_role(promise),canonical_role(requirement)
    levels={"unspecified":0,"fringe":1,"rotation":2,
            "regular_starter":3,"key_player":4}
    if requirement in ("none","unspecified"):
        return True
    return promise in levels and requirement in levels and levels[promise]>=levels[requirement]


def phase_for_age(age):
    if type(age) is not int or not 15 <= age <= 55:
        return "unassessed"
    if age <= 23:
        return "development"
    if age <= 29:
        return "prime"
    return "veteran"


def required_role_for_move(*,legacy_decision,prestige_deficit,sport_deficit,
                           division_drop,overall,phase,rival_pressure=0):
    """A promise cannot rescue a genuinely huge sporting drop."""
    if phase == "unassessed":
        return "unassessed"
    if (legacy_decision == "needs_assurances"
        or prestige_deficit >= {"development":30,"prime":22,"veteran":34}[phase]
        or rival_pressure >= 13):
        if (division_drop >= 1 and type(overall) is int and overall >= 82
                and phase == "prime" and sport_deficit >= 8):
            return "key_player"
        return "regular_starter"
    return "none"


def evaluate_player_choice(*,buyer_tier,seller_tier,buyer_score,seller_score,
                           buyer_prestige,seller_prestige,overall,age,
                           role_promise="unspecified",competitor_pressure=0):
    """A deterministic, auditable decision using two *separate* club ratings.

    Existing hard sporting refusals are preserved. Money is intentionally
    NOT passed in: it cannot override a sporting refusal. Price and contract
    length are agent-negotiation decisions in a separate function.
    """
    if role_promise not in ROLES:
        raise ValueError("Unrecognised role promise")
    if type(competitor_pressure) is not int or not 0<=competitor_pressure<=60:
        raise ValueError("Competing-interest pressure must be between 0 and 60")
    values=(buyer_tier,seller_tier,buyer_score,seller_score,buyer_prestige,
            seller_prestige,overall)
    if (any(type(v) is not int for v in values)
        or not all(1<=v<=4 for v in (buyer_tier,seller_tier))
        or not all(0<=v<=100 for v in (buyer_score,seller_score,
                                       buyer_prestige,seller_prestige))
        or not 1<=overall<=99):
        return _review("Incomplete sourced ratings or career prestige snapshot")
    phase=phase_for_age(age)
    if phase=="unassessed":
        return _review("Player age is unknown; no fictional career-stage preference is inferred")
    base=assess_player_interest(
        buyer_tier=buyer_tier,seller_tier=seller_tier,
        buyer_score=buyer_score,seller_score=seller_score,player_overall=overall)
    sport_deficit=seller_score-buyer_score
    prestige_deficit=seller_prestige-buyer_prestige
    division_drop=buyer_tier-seller_tier
    breakdown={
        "sporting_gap":buyer_score-seller_score,
        "prestige_gap":buyer_prestige-seller_prestige,
        "tier_difference":division_drop,
        "player_phase":phase,
        "player_age":age,
        "player_overall":overall,
        "competing_pressure":competitor_pressure,
        "buyer_prestige":buyer_prestige,"seller_prestige":seller_prestige,
        "buyer_sporting":buyer_score,"seller_sporting":seller_score,
        "policy_version":DECISION_VERSION,
    }
    if not base["can_negotiate"]:
        return {**breakdown,"decision":base["decision"],"can_negotiate":False,
                "required_role":"unavailable",
                "reason":"Sporting barrier: "+base["reason"]}
    # Elite players in their prime will not accept a strongly worse sporting
    # *and* institutional move for a nominal wage premium or starter promise.
    if (phase=="prime" and overall>=85 and division_drop>=1
        and sport_deficit>=10 and prestige_deficit>=25):
        return {**breakdown,"decision":"uninterested","can_negotiate":False,
                "required_role":"unavailable",
                "reason":"Peak elite player: major sporting and prestige downgrade; no wage override"}
    need=required_role_for_move(
        legacy_decision=base["decision"],
        prestige_deficit=prestige_deficit,sport_deficit=sport_deficit,
        division_drop=division_drop,overall=overall,phase=phase,
        rival_pressure=competitor_pressure)
    satisfied=(need=="none"
               or role_satisfies(role_promise,need))
    if not satisfied:
        reason=(
            f"{phase.capitalize()} player: current sporting difference "
            f"{-sport_deficit:+d}, historical prestige difference "
            f"{-prestige_deficit:+d}; {need.replace('_',' ')} role required."
        )
        if competitor_pressure>=13:
            reason+=" An actual sandbox rival bid raises the player's expectations."
        return {**breakdown,"decision":"needs_assurances","can_negotiate":True,
                "required_role":need,"role_satisfied":False,"reason":reason}
    summary=(f"{phase.capitalize()} player: sporting change {-sport_deficit:+d}, "
             f"institutional prestige change {-prestige_deficit:+d}; "
             f"playing-time assessment {'satisfied' if need!='none' else 'does not demand a guarantee'}.")
    if competitor_pressure>=13:
        summary+=" Simulated rival interest may raise contract expectations."
    return {**breakdown,"decision":"open_to_talks","can_negotiate":True,
            "required_role":need,"role_satisfied":True,"reason":summary}


def _review(reason):
    return {"decision":"review","can_negotiate":False,
            "required_role":"unassessed","policy_version":DECISION_VERSION,
            "reason":reason}


def competitor_advantage(*,rival_sporting,rival_prestige,buyer_sporting,buyer_prestige):
    """Meaningful rival bid advantage, not fictional AI interest."""
    args=(rival_sporting,rival_prestige,buyer_sporting,buyer_prestige)
    if any(type(x) is not int or x<0 or x>100 for x in args):
        return 0
    # A reasonable sporting opportunity counts more than historic brand.
    difference=(rival_sporting-buyer_sporting)*0.55
    difference+=(rival_prestige-buyer_prestige)*0.22
    return min(60,max(0,round(difference)))


def agent_minimum_wage(*,base_wage,choice,competing_bid=False):
    """Fictional demand with finite increase for difficult career trade-offs.

    Known base wage is determined by the EA overall wage proxy already used
    by the transfer desk, NOT a real-life salary.
    """
    if type(base_wage) is not int or base_wage<0:
        raise ValueError("Invalid baseline weekly wage")
    if choice["decision"] in ("uninterested","review"):
        return None
    sport_penalty=max(0,-choice["sporting_gap"])
    prestige_penalty=max(0,-choice["prestige_gap"])
    stage=choice["player_phase"]
    prestige_weight={"development":0.002,"prime":0.0035,"veteran":0.0018}[stage]
    premium=(sport_penalty*0.008+prestige_penalty*prestige_weight+
             max(0,choice["tier_difference"])*0.035)
    if choice.get("competing_pressure",0)>=13 and competing_bid:
        premium+=0.08
    premium=min(0.70,max(0.0,premium))
    return min(350_000,max(1000,round(base_wage*(1+premium)/500)*500))


def contract_length_consideration(*,phase,years):
    if type(years) is not int or years not in (1,2,3,4,5):
        raise ValueError("Contract years must be 1–5")
    # A development prospect prefers some security; a veteran isn't forced
    # to commit to a long-term deal. This remains a soft counter factor.
    if phase=="development" and years==1:
        return "Short deal for a developing player may require additional wage security"
    if phase=="prime" and years==1:
        return "One-year deal for a peak-age player may require improved terms"
    return None


# V2 context-aware player decision engine.
DECISION_V2_VERSION = "player-decisions-v2"
PLAYER_CURRENT_ROLES = ("unknown","key_player","regular_starter","rotation","fringe")
RENEWAL_STATES = ("unknown","renewal_offered","not_offered")
# Participation is an explicit current/next-season fact or scenario, never
# inferred from the club name, starting league position or prestige.
EUROPE_LEVELS = {
    "unknown": None,
    "none": 0,
    "conference_league": 2,
    "europa_league": 3,
    "champions_league": 5,
}
EUROPE_LABELS = {
    "unknown": "Not verified",
    "none": "No continental football",
    "conference_league": "Conference League",
    "europa_league": "Europa League",
    "champions_league": "Champions League",
}


def _money_floor_v2(*,current_wage,buyer_tier,seller_tier,
                    buyer_score,seller_score,buyer_prestige,seller_prestige,
                    overall,age,current_role,transfer_listed,renewal_status,
                    competitor_pressure,buyer_europe="none",seller_europe="none",
                    role_promise="unspecified"):
    """Weekly minimum for considering a move, not a verified wage or price."""
    from math import ceil
    outgoing=transfer_listed or renewal_status=="not_offered"
    decline=max(0,seller_score-buyer_score)
    heritage=max(0,seller_prestige-buyer_prestige)
    tier_drop=max(0,buyer_tier-seller_tier)
    europe_drop=max(0,EUROPE_LEVELS[seller_europe]-EUROPE_LEVELS[buyer_europe])
    regular=canonical_role(current_role) in ("regular_starter","key_player")
    prime=24<=age<=31
    elite=overall>=88 and prime and regular
    downgrade=decline>=5 or heritage>=12 or tier_drop>=1 or europe_drop>=2
    premium=(decline*0.010 + heritage*0.006 +
             tier_drop*0.055 + europe_drop*0.05 +
             (0.10 if regular and downgrade and not outgoing else 0.0) +
             (0.06 if competitor_pressure>=13 else 0.0))
    if current_role in ("fringe","rotation") and role_satisfies(
            role_promise,"regular_starter"):
        # A reliable starting place is a meaningful non-cash benefit for a
        # backup, but it does not erase a severe financial downgrade.
        minimum_multiplier=max(0.90 if outgoing else 1.0,
                               1.0+premium*(0.25 if outgoing else 0.35))
    elif outgoing and current_role in ("fringe","rotation"):
        minimum_multiplier=max(0.90,1.0+premium*0.45)
    elif outgoing and elite and downgrade:
        # CL-to-no-Europe for an outgoing peak-age regular needs compelling
        # financial terms *and* a key-player promise, not a token raise.
        minimum_multiplier=max(1.75 if europe_drop>=5 else 1.50,1.0+premium)
    else:
        minimum_multiplier=1.0+premium
    if not outgoing and regular and downgrade:
        minimum_multiplier=max(1.20,minimum_multiplier)
    # A currently contracted player must not be treated as earning the
    # fictional overall-based proxy. We use the explicitly supplied current
    # wage as the financial benchmark instead.
    return int(ceil(current_wage*minimum_multiplier/500)*500)


def evaluate_player_choice_v2(*,buyer_tier,seller_tier,buyer_score,seller_score,
                              buyer_prestige,seller_prestige,overall,age,
                              current_wage=None,current_role="unknown",
                              transfer_listed=None,renewal_status="unknown",
                              offered_wage=None,role_promise="unspecified",
                              competitor_pressure=0,buyer_europe="unknown",
                              seller_europe="unknown"):
    """Context-aware approach decision, not a statement of real consent.

    An unverified wage/role/listed status/renewal is NEVER silently
    filled by the EA overall or a club-level proxy. No one is deemed to
    accept terms when a wage offer is not yet known.
    """
    if current_role not in PLAYER_CURRENT_ROLES:
        raise ValueError("Unknown current squad role")
    if buyer_europe not in EUROPE_LEVELS or seller_europe not in EUROPE_LEVELS:
        raise ValueError("European participation must be explicitly selected or unknown")
    if renewal_status not in RENEWAL_STATES:
        raise ValueError("Unknown contract renewal status")
    if transfer_listed is not None and type(transfer_listed) is not bool:
        raise ValueError("Transfer-listing must be explicitly yes, no or unknown")
    if current_wage is not None and (type(current_wage) is not int or
                                     not 0<=current_wage<=1_000_000):
        raise ValueError("Invalid current weekly wage")
    if offered_wage is not None and (type(offered_wage) is not int or
                                     not 0<=offered_wage<=1_000_000):
        raise ValueError("Invalid offered weekly wage")
    if role_promise not in ROLES:
        raise ValueError("Unrecognised role promise")
    current_role=canonical_role(current_role)
    role_promise=canonical_role(role_promise)
    if type(competitor_pressure) is not int or not 0<=competitor_pressure<=60:
        raise ValueError("Competing pressure must be 0–60")
    basic=(buyer_tier,seller_tier,buyer_score,seller_score,
           buyer_prestige,seller_prestige,overall)
    if (any(type(v) is not int for v in basic) or
        not all(1<=tier<=4 for tier in (buyer_tier,seller_tier)) or
        not all(0<=value<=100 for value in
                (buyer_score,seller_score,buyer_prestige,seller_prestige)) or
        not 1<=overall<=99 or phase_for_age(age)=="unassessed"):
        return {"policy_version":DECISION_V2_VERSION,"decision":"review",
                "can_negotiate":False,"required_role":"unassessed",
                "reason":"Player age, rating or comparable club scores are unavailable"}
    phase=phase_for_age(age)
    shared={
        "policy_version":DECISION_V2_VERSION,
        "player_phase":phase,"player_age":age,"player_overall":overall,
        "sporting_gap":buyer_score-seller_score,
        "prestige_gap":buyer_prestige-seller_prestige,
        "tier_difference":buyer_tier-seller_tier,
        "buyer_sporting":buyer_score,"seller_sporting":seller_score,
        "buyer_prestige":buyer_prestige,"seller_prestige":seller_prestige,
        "current_wage":current_wage,"offered_wage":offered_wage,
        "current_role":current_role,"transfer_listed":transfer_listed,
        "renewal_status":renewal_status,
        "buyer_europe":buyer_europe,"seller_europe":seller_europe,
        "european_gap":(None if "unknown" in (buyer_europe,seller_europe)
                        else EUROPE_LEVELS[buyer_europe]-EUROPE_LEVELS[seller_europe]),
        "competing_pressure":competitor_pressure,
    }
    def decision(label,reason,*,required_role="none",floor=None,
                 issue="none",role_satisfied=None):
        # Preserve the public decision code for existing career integrations,
        # but distinguish missing playing-time assurance from a wage counter.
        return {**shared,"decision":label,
                "can_negotiate":label in ("needs_assurances","open_to_talks"),
                "required_role":required_role,"minimum_wage":floor,
                "issue":issue,"role_satisfied":role_satisfied,
                "wage_shortfall":(max(0,floor-offered_wage)
                    if floor is not None and offered_wage is not None else None),
                "reason":reason}
    if current_wage is None or current_role=="unknown" or transfer_listed is None:
        return decision("review","Current wage, present squad role and transfer-list status must be supplied; they cannot be inferred from an overall rating")
    if renewal_status=="unknown":
        return decision("review","Contract renewal intentions are unknown. Do not assume the current club will release this player")
    if "unknown" in (buyer_europe,seller_europe):
        return decision("review",
            "Continental participation at both clubs must be explicitly recorded. "
            "A Champions League place must not be inferred from squad ability or prestige")
    baseline=assess_player_interest(
        buyer_tier=buyer_tier,seller_tier=seller_tier,
        buyer_score=buyer_score,seller_score=seller_score,
        player_overall=overall)
    regular=current_role in ("key_player","regular_starter")
    elite=regular and 24<=age<=31 and overall>=88
    sport_deficit=seller_score-buyer_score
    prestige_deficit=seller_prestige-buyer_prestige
    tier_drop=buyer_tier-seller_tier
    # Sporting appeal alone is too harsh on an overlooked squad member.
    # A bench player can CONSIDER a meaningful step down if the new club can
    # credibly promise starts and meet the financial terms. Still reject
    # implausibly vast downgrades and elite players in this exception.
    playing_time_exception=(not baseline["can_negotiate"]
        and current_role in ("rotation","fringe") and overall<82
        and (
            (sport_deficit<45 and tier_drop<=2)
            # Experienced third-choice/fringe players with modest ratings
            # can legitimately drop three divisions for a starting job.
            # This is provisional interest ONLY; wage and role assurances
            # still independently determine whether they accept.
            or (current_role=="fringe" and age>=29 and overall<=72
                and tier_drop==3 and sport_deficit<55)
        ))
    if not baseline["can_negotiate"] and not playing_time_exception:
        return decision("uninterested","Severe sporting downgrade: "+baseline["reason"])
    europe_drop=EUROPE_LEVELS[seller_europe]-EUROPE_LEVELS[buyer_europe]
    downgrade=(sport_deficit>=5 or prestige_deficit>=12
               or tier_drop>=1 or europe_drop>=2)
    outgoing=transfer_listed or renewal_status=="not_offered"
    # A permanent move DOWN the pyramid is not a credible next step for an
    # established, contracted top-flight player in his prime. Previously
    # only 88+ elite starters were protected; a 79-rated Arsenal regular
    # could join a Championship club on a routine contract, which made
    # sporting downgrade checks toothless in real 92-club simulations.
    # A genuinely listed player or one being released remains negotiable.
    high_level_downgrade=(seller_tier==1 and tier_drop>=1
                          and overall>=78)
    # Permanent moves into a lower division are an exceptional career
    # choice for prime-age top-flight players, even those momentarily out
    # of the starting XI. A loan would be the normal route for young stars,
    # but the game does not yet implement loans. A listed or non-renewed
    # older backup may consider a move under distinct wage/role conditions.
    if (high_level_downgrade and
            (age<30 or (overall>=79 and age<34))):
        return decision("uninterested",
            "A high-rated Premier League player in his athletic prime "
            "would not normally choose a permanent move into a lower "
            "division, even if currently out of favour. Short-term loans "
            "and exceptional late-career exits require separate modelling.")
    if high_level_downgrade and not outgoing:
        return decision("uninterested",
            "Established Premier League player is neither transfer listed "
            "nor being released. A permanent lower-division offer has no "
            "credible career or contract incentive.")
    if (high_level_downgrade and
            current_role in ("key_player","regular_starter") and age<=33):
        return decision("uninterested",
            "Established top-flight first-team player is not available "
            "for a routine permanent lower-division transfer.")
    if elite and europe_drop>=3 and not outgoing:
        return decision("uninterested",
            "Established elite first-team regular would lose "+
            EUROPE_LABELS[seller_europe]+" football for "+
            EUROPE_LABELS[buyer_europe]+
            ". Without transfer-listing or confirmed non-renewal, "
            "a salary offer or squad-role promise does not explain this move")
    if elite and downgrade and not outgoing:
        return decision("uninterested",
            "Established elite first-team regular with a contract opportunity to stay: "
            "a lower-prestige or weaker club is not a realistic destination. "
            "A verified transfer-listing or non-renewal circumstance would be needed")
    floor=_money_floor_v2(
        current_wage=current_wage,buyer_tier=buyer_tier,seller_tier=seller_tier,
        buyer_score=buyer_score,seller_score=seller_score,
        buyer_prestige=buyer_prestige,seller_prestige=seller_prestige,
        overall=overall,age=age,current_role=current_role,
        transfer_listed=transfer_listed,renewal_status=renewal_status,
        competitor_pressure=competitor_pressure,
        buyer_europe=buyer_europe,seller_europe=seller_europe,
        role_promise=role_promise)
    if high_level_downgrade:
        # Even a genuine ageing, listed top-flight reserve should receive
        # financial security instead of accepting a nominal wage uplift.
        floor=max(floor,int(current_wage*1.75))
    role_needed="none"
    if high_level_downgrade and current_role!="fringe":
        role_needed="key_player"
    elif elite and downgrade:
        role_needed="key_player"
    elif playing_time_exception:
        role_needed="regular_starter"
    elif baseline["decision"]=="needs_assurances" or (regular and downgrade) or (
            prestige_deficit>=22 and phase=="prime") or (
            phase=="prime" and europe_drop>=3):
        role_needed="regular_starter"
    elif current_role=="rotation" and sport_deficit>=10:
        role_needed="regular_starter"
    role_satisfied=role_satisfies(role_promise,role_needed)
    if offered_wage is not None and current_wage>0 and downgrade and (
            offered_wage < current_wage*0.60):
        return decision("uninterested",
            f"Proposed £{offered_wage:,}/week is far below the "
            f"current £{current_wage:,}/week during a sporting/prestige downgrade",
            required_role=role_needed,floor=floor)
    if offered_wage is None:
        remaining=("Salary terms are not yet available"
                   if role_satisfied else
                   f"A {ROLE_LABELS[role_needed]} guarantee is also missing")
        return decision("needs_assurances",
            f"Current salary £{current_wage:,}/week and "
            f"{ROLE_LABELS[current_role]} squad status are documented. "
            f"Minimum wage benchmark £{floor:,}/week. {remaining}. "+
            ("A move to a less prestigious club remains possible if this "
             "backup is given credible regular starts and suitable pay."
             if playing_time_exception else ""),
            required_role=role_needed,floor=floor,
            issue="wage" if role_satisfied else "wage_and_role",
            role_satisfied=role_satisfied)
    if offered_wage<floor:
        opportunity_note=(
            f"; moving from {EUROPE_LABELS[seller_europe]} to "
            f"{EUROPE_LABELS[buyer_europe]} is a further sporting downgrade"
            if europe_drop>=2 else "")
        role_note=(f"The promised {ROLE_LABELS[role_promise]} role already "
                   f"meets the {ROLE_LABELS[role_needed]} requirement. "
                   if role_satisfied and role_needed!="none" else
                   f"The {ROLE_LABELS[role_needed]} squad-role guarantee "
                   "is also missing. " if not role_satisfied else "")
        return decision("needs_assurances",
            role_note+f"Salary £{offered_wage:,}/week is £{floor-offered_wage:,} "
            f"below the £{floor:,}/week benchmark (current pay "
            f"£{current_wage:,}/week)"+opportunity_note,
            required_role=role_needed,floor=floor,
            issue="wage" if role_satisfied else "wage_and_role",
            role_satisfied=role_satisfied)
    if not role_satisfied:
        return decision("needs_assurances",
            f"Offered salary meets the £{floor:,}/week benchmark, but "
            f"the {ROLE_LABELS[role_needed]} squad-role guarantee is missing",
            required_role=role_needed,floor=floor,
            issue="role",role_satisfied=False)
    return decision("open_to_talks",
        f"Specific context supports provisional talks: salary £{offered_wage:,}/week "
        f"versus current £{current_wage:,}/week, {current_role.replace('_',' ')} "
        f"at present club, {'listed for transfer' if transfer_listed else 'not listed'}, "
        f"renewal {renewal_status.replace('_',' ')}. "
        f"European opportunity: {EUROPE_LABELS[seller_europe]} at current club "
        f"versus {EUROPE_LABELS[buyer_europe]} at interested club. " +
        ("A reliable starting role offers a career opportunity despite "
         "the sporting downgrade. " if playing_time_exception else "")+
        "No player acceptance or transfer is implied",
        required_role=role_needed,floor=floor,
        role_satisfied=True)


def agent_minimum_wage_v2(*,choice):
    """Reuses the player's current documented/simulated wage—not an EA proxy."""
    if choice.get("decision") in ("review","uninterested"):
        return None
    return choice.get("minimum_wage")
