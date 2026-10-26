"""Independent FC27 club-led transfer-market activity in the 30-minute window.

A market interval is a CHECKPOINT, never a quota of offers or registrations.
Each solvent AI club makes its own repeatable scouting/commitment decision.
Confirmed activity is persisted before negotiations so polling, retries and
restarts neither regenerate opportunity rolls nor duplicate transfers.
No global 112-market-attempt scheduler is used for FC27.
"""
from collections import defaultdict

from world_ai_tactics import preferred_formation,tactical_needs
from world_fc27_ai_recruitment import (
    read_fc27_profiles,buyer_recruitment_priority)
from world_fc27_market_choices import pursue_transfer
from world_squad_planner import projected_squads,lane_of

VERSION="fc27-independent-club-market-v3-unmet-needs"
# Separates FC27 AI club IDs/ticks from the immutable legacy 112 slot keys.
FC27_SLOT_BASE=100000000
FC27_SLOT_INTERVAL=1000000

SCHEMA="""
CREATE TABLE IF NOT EXISTS world_fc27_market_intervals(
 window_id INTEGER NOT NULL,
 interval_index INTEGER NOT NULL,
 eligible_clubs INTEGER NOT NULL,
 active_clubs INTEGER NOT NULL,
 activity_scale_qa INTEGER NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(window_id,interval_index)
);
CREATE TABLE IF NOT EXISTS world_fc27_market_club_intents(
 window_id INTEGER NOT NULL,
 interval_index INTEGER NOT NULL,
 club_id INTEGER NOT NULL,
 source_priority REAL NOT NULL,
 processed INTEGER NOT NULL DEFAULT 0,
 agreed_offer_id INTEGER,
 PRIMARY KEY(window_id,interval_index,club_id)
);
CREATE INDEX IF NOT EXISTS world_fc27_market_intents_pending
 ON world_fc27_market_club_intents(window_id,interval_index,processed);
"""

def initialise_fc27_market_schedule(conn):
    conn.executescript(SCHEMA)
    from world_fc27_decision_audit import initialize_decision_audit
    initialize_decision_audit(conn)
    conn.commit()

def is_fc27_market(conn,*,career_id):
    """FC27 extension only, not pre-existing PES/English world careers."""
    row=conn.execute("""SELECT dataset_id FROM world_career_saves
       WHERE career_id=?""",(career_id,)).fetchone()
    if row is None or row[0]!="fc27-warehouse-659-mens-2026-27":
        return False
    if not conn.execute("""SELECT 1 FROM sqlite_master
       WHERE type='table' AND name='world_fc27_club_ai_context'""").fetchone():
        return False
    return bool(conn.execute("""SELECT 1 FROM world_fc27_club_ai_context
       WHERE dataset_id=? LIMIT 1""",(row[0],)).fetchone())

def club_market_interest(*,priority,profile,draw,activity_scale_qa=1,
                         unattended_intervals=0):
    """Model probability of scouting activity, not a deal count.

    All clubs have a nonzero chance; need/ambition drive participation.
    3x is an isolated QA sensitivity scenario, not deployed scheduling.
    A club still separately decides whether to proceed to negotiations.
    """
    if (type(draw) is not int or not 0<=draw<1000000 or
            activity_scale_qa not in (1,3) or
            type(unattended_intervals) is not int or
            not 0<=unattended_intervals<=30):
        raise ValueError("Invalid independent club market draw")
    ambition=profile.get("ambition_level",50) if profile else 50
    board_pressure=profile.get("pressure_to_improve",50) if profile else 50
    financial_stress=profile.get("financial_pressure_index",50) if profile else 50
    urgency=max(-35,min(120,priority))
    # Board ambition and performance pressure make an already strong club
    # proactively search for genuine XI improvements; a full starting XI
    # does not mean recruitment stops. Financially stretched teams still
    # have some ability to scout but become more selective.
    # This is a per-club *decision*, not a quota or an elite club exception.
    base=(.082+urgency*.00069+(ambition-50)*.00055+
          max(0,ambition-73)*.0046+
          max(0,board_pressure-65)*.0019-
          max(0,financial_stress-60)*.0015)
    # A genuine unresolved recruitment objective persists across the window.
    # Repeated inaction gradually raises consideration, without a mandated
    # transfer (or even a guaranteed search) and without club-name overrides.
    # Reset after any actual search; previous deals/roster changes already
    # affect the live priority above.
    unresolved=max(0,min(115,priority-15))
    persistence=min(.22,unattended_intervals*(.011+unresolved*.00042))
    return draw/1000000<min(.82,max(.035,base+persistence)*activity_scale_qa)

def fc27_market_slot(interval_index,club_id):
    if not (type(interval_index) is int and 0<=interval_index<30
            and type(club_id) is int and 0<club_id<FC27_SLOT_INTERVAL):
        raise ValueError("FC27 market slot outside collision-free domain")
    return FC27_SLOT_BASE+interval_index*FC27_SLOT_INTERVAL+club_id

def _club_departures(conn,career_id,window_id):
    from world_squad_planner import lane_of
    outgoing=defaultdict(set)
    for club,pos in conn.execute("""SELECT o.selling_club_id,p.primary_position
        FROM world_career_offer_events e
        JOIN world_career_offers o ON o.offer_id=e.offer_id
        JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
        JOIN world_players p ON p.player_id=o.player_id
        WHERE wo.window_id=? AND o.career_id=?
          AND e.event_type='ai_world_signed'""",(window_id,career_id)):
        lane=lane_of(pos)
        if lane:outgoing[club].add(lane)
    return outgoing

def plan_fc27_market_interval(conn,*,career_id,window_id,interval_index,
                               when,activity_scale_qa=1):
    """Persist each club's independent choice BEFORE any transfer negotiations."""
    from world_live_market import _stable
    if activity_scale_qa not in (1,3):
        raise ValueError("QA scenario may only be 1 or 3")
    if not is_fc27_market(conn,career_id=career_id):
        raise ValueError("Not an FC27 club-led market")
    prior=conn.execute("""SELECT activity_scale_qa FROM
      world_fc27_market_intervals WHERE window_id=? AND interval_index=?""",
      (window_id,interval_index)).fetchone()
    if prior:
        if prior[0]!=activity_scale_qa:
            raise ValueError("Cannot change activity scenario during a planned interval")
        return
    dataset,manager=conn.execute("""SELECT dataset_id,manager_club_id
       FROM world_career_saves WHERE career_id=?""",(career_id,)).fetchone()
    profiles=read_fc27_profiles(conn,dataset=dataset)
    squads=projected_squads(conn,career_id=career_id,dataset=dataset)
    departures=_club_departures(conn,career_id,window_id)
    arrivals=dict(conn.execute("""SELECT o.buying_club_id,COUNT(*)
      FROM world_career_offer_events e JOIN world_career_offers o
        ON o.offer_id=e.offer_id
      JOIN world_career_preseason_window_offers wo ON wo.offer_id=o.offer_id
      WHERE wo.window_id=? AND o.career_id=?
        AND e.event_type='ai_world_signed'
      GROUP BY o.buying_club_id""",(window_id,career_id)).fetchall())
    funded={club for club,trans,wages,fees,wage_use in conn.execute(
      """SELECT club_id,transfer_budget,weekly_wage_budget,
                committed_fees,committed_wages
         FROM world_career_club_ledger WHERE career_id=?""",(career_id,))
       if trans>fees and wages>wage_use}
    from world_fc27_decision_audit import save_evaluations
    # Read earlier checks in one indexed query, rather than N*12 queries.
    # Only a real search resets unaddressed market interest: not scouting or
    # scouting and holding cash both leave the need under consideration.
    prior_evaluations=conn.execute("""SELECT club_id,stage FROM
        world_fc27_market_club_evaluations WHERE window_id=?
        AND interval_index<? ORDER BY club_id,interval_index DESC""",
        (window_id,interval_index)).fetchall()
    # Count consecutive earlier inaction only until the last real search.
    unattended={}
    closed=set()
    for club,stage in prior_evaluations:
        if club in closed:
            continue
        if stage=="proceeded_to_search":
            closed.add(club)
        elif stage in ("did_not_scout","scouted_but_held"):
            unattended[club]=unattended.get(club,0)+1
        else:
            closed.add(club)
    possibilities=0
    plans=[]
    evaluation_rows=[]
    for club in sorted(profiles.keys() & squads.keys()):
        if club==manager:
            continue
        if club not in funded:
            evaluation_rows.append((window_id,interval_index,club,None,
                                    None,None,"no_budget_or_wage_headroom"))
            continue
        possibilities+=1
        profile=profiles[club]
        formation=tactical_needs(preferred_formation(
            club_id=club,profile=profile))["starting_roles"]
        priority=buyer_recruitment_priority(
            squads,club=club,profile=profile,
            departed_lanes=departures[club],starting_roles=formation,
            previous_signings=arrivals.get(club,0),
            stable_variation=_stable(career_id,window_id,interval_index,
                        club,VERSION,"variation")%26)
        scout_draw=_stable(career_id,window_id,interval_index,
                           club,VERSION,"scout")%1000000
        commitment_draw=_stable(career_id,window_id,interval_index,
                                club,VERSION,"commit")%1000
        if not club_market_interest(priority=priority,profile=profile,
                draw=scout_draw,activity_scale_qa=activity_scale_qa,
                unattended_intervals=unattended.get(club,0)):
            evaluation_rows.append((window_id,interval_index,club,
                priority,scout_draw,commitment_draw,"did_not_scout"))
            continue
        if not pursue_transfer(priority=priority,profile=profile,
                draw=commitment_draw):
            evaluation_rows.append((window_id,interval_index,club,
                priority,scout_draw,commitment_draw,"scouted_but_held"))
            continue
        evaluation_rows.append((window_id,interval_index,club,
            priority,scout_draw,commitment_draw,"proceeded_to_search"))
        plans.append((window_id,interval_index,club,priority))
    # Deterministic fair order. Clubs are never removed merely because an
    # earlier club signed a player; later clubs recheck actual availability.
    conn.execute("""INSERT INTO world_fc27_market_intervals
      (window_id,interval_index,eligible_clubs,active_clubs,
       activity_scale_qa,created_at) VALUES(?,?,?,?,?,?)""",
       (window_id,interval_index,possibilities,len(plans),
        activity_scale_qa,when.isoformat()))
    conn.executemany("""INSERT INTO world_fc27_market_club_intents
      (window_id,interval_index,club_id,source_priority)
      VALUES(?,?,?,?)""",plans)
    save_evaluations(conn,evaluation_rows)
    conn.commit()

def process_fc27_market_interval(conn,*,career_id,window_id,
                                 interval_index,when,activity_scale_qa=1):
    """Execute every planned club-led search, without a transaction quota."""
    from world_ai_world import consider_ai_world_deal
    plan_fc27_market_interval(conn,career_id=career_id,window_id=window_id,
        interval_index=interval_index,when=when,
        activity_scale_qa=activity_scale_qa)
    pending=conn.execute("""SELECT club_id FROM world_fc27_market_club_intents
       WHERE window_id=? AND interval_index=? AND processed=0
       ORDER BY source_priority DESC,club_id""",
       (window_id,interval_index)).fetchall()
    for (club,) in pending:
        offered=consider_ai_world_deal(conn,career_id=career_id,
            window_id=window_id,slot=fc27_market_slot(interval_index,club),
            now=when,buying_club_id=club)
        conn.execute("""UPDATE world_fc27_market_club_intents
          SET processed=1,agreed_offer_id=?
          WHERE window_id=? AND interval_index=? AND club_id=?""",
          (offered,window_id,interval_index,club))
        conn.commit()
    return conn.execute("""SELECT eligible_clubs,active_clubs FROM
       world_fc27_market_intervals WHERE window_id=? AND interval_index=?""",
       (window_id,interval_index)).fetchone()
