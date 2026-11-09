"""FC27 player wage ambitions and manager-led contract renewals.

Source wages are EA game data; market salaries are *estimates* based on
comparable source-rated peers, not verified real-world contractual demands.
No transfer permission or forced sale follows from a valuation gap.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from statistics import median
import hashlib

DATASET="fc27-warehouse-659-mens-2026-27"
MODEL="fc27-peer-wage-ambition-v1"

SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_contract_renewals (
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 old_weekly_wage INTEGER NOT NULL CHECK(old_weekly_wage>=0),
 peer_weekly_wage INTEGER CHECK(peer_weekly_wage>=0),
 demand_weekly_wage INTEGER NOT NULL CHECK(demand_weekly_wage>=0),
 offered_weekly_wage INTEGER CHECK(offered_weekly_wage>=0),
 contract_years INTEGER CHECK(contract_years BETWEEN 1 AND 5),
 status TEXT NOT NULL CHECK(status IN (
   'requested','negotiating','countered','accepted_terms',
   'agreed_future','completed','declined','withdrawn','expired')),
 initiated_by TEXT NOT NULL CHECK(initiated_by IN ('player','manager')),
 rounds INTEGER NOT NULL DEFAULT 0 CHECK(rounds BETWEEN 0 AND 6),
 signed_at TEXT, effective_date TEXT,
 model_version TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,window_id,player_id)
);
CREATE INDEX IF NOT EXISTS world_renewal_player_status ON
 world_career_contract_renewals(career_id,player_id,status);
CREATE TABLE IF NOT EXISTS world_career_contract_request_sweeps (
 career_id TEXT NOT NULL, window_id INTEGER NOT NULL,
 swept_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,window_id)
);
"""

def initialise_contract_renewals(conn):
    conn.executescript(SCHEMA)
    conn.commit()

def _stable(*parts):
    return int.from_bytes(hashlib.sha256(
        (MODEL+"|"+ "|".join(map(str,parts))).encode()).digest()[:8],"big")/2**64

def _role_adjustment(role):
    return {"key_player":1.10,"regular_starter":1.05,
            "rotation":.97,"fringe":.88}.get(role,1.0)

def _target(conn,career_id,player_id):
    row=conn.execute("""SELECT c.dataset_id,c.manager_club_id,
       c.pes_lock_date,c.next_summer_date,r.club_id,p.full_name,
       p.primary_position,p.birth_date,x.overall,
       COALESCE(pc.current_wage_weekly,cs.weekly_wage_gbp),
       COALESCE(pc.current_role,lc.squad_role_estimate),
       cs.expires_on
       FROM world_career_saves c
       JOIN world_career_registrations r ON r.career_id=c.career_id
       JOIN world_players p ON p.player_id=r.player_id
       JOIN world_dataset_ratings x ON x.player_id=r.player_id
           AND x.dataset_id=c.dataset_id
       LEFT JOIN world_career_player_circumstances pc
         ON pc.career_id=c.career_id AND pc.player_id=r.player_id
       LEFT JOIN world_career_contract_snapshots cs
         ON cs.career_id=c.career_id AND cs.player_id=r.player_id
       LEFT JOIN world_career_live_player_context lc
         ON lc.career_id=c.career_id AND lc.player_id=r.player_id
         AND lc.window_id=(SELECT window_id FROM world_career_preseason_windows
           WHERE career_id=c.career_id ORDER BY window_id DESC LIMIT 1)
       WHERE c.career_id=? AND r.player_id=? AND c.state='sandbox'""",
       (career_id,player_id)).fetchone()
    if row is None or row[0]!=DATASET:raise ValueError("FC27 career player not found")
    if row[1]!=row[4]:raise ValueError("Only players currently at your club can renew")
    if row[9] is None:raise ValueError("Unknown current wages; do not invent the contract")
    return dict(dataset=row[0],club=row[1],lock=row[2],summer=row[3],
        player_id=player_id,name=row[5],position=row[6],birth=row[7],
        overall=row[8],wage=int(row[9]),role=row[10],expires=row[11])

def _peer_market_wage(conn,*,dataset,club_id,overall,position):
    """Median source salary for close-rated players at comparable clubs.

    Prefer the same source competition; fall back to all source players in
    the same position family only if peer coverage is insufficient.
    """
    from world_ai_bidding import position_family
    current_league=conn.execute("""SELECT competition_id FROM world_dataset_entries
        WHERE dataset_id=? AND club_id=? ORDER BY competition_id LIMIT 1""",
        (dataset,club_id)).fetchone()
    league=current_league[0] if current_league else None
    players=conn.execute("""SELECT d.weekly_wage_gbp,x.overall,
        p.primary_position,d.club_id,
        (SELECT e.competition_id FROM world_dataset_entries e
            WHERE e.dataset_id=d.dataset_id AND e.club_id=d.club_id
            ORDER BY e.competition_id LIMIT 1) AS competition_id
        FROM world_dataset_contract_snapshots d
        JOIN world_dataset_ratings x
          ON x.dataset_id=d.dataset_id AND x.player_id=d.player_id
        JOIN world_players p ON p.player_id=d.player_id
        WHERE d.dataset_id=? AND x.overall BETWEEN ? AND ?
          AND d.weekly_wage_gbp > 0""",
        (dataset,max(1,overall-6),min(99,overall+6))).fetchall()
    family=position_family(position)
    matches=[]
    for wage,rating,pos,other,comp in players:
        if other==club_id:continue
        if position_family(pos)!=family:continue
        # An OVR point alters weight smoothly; no fixed salary by rating.
        comparable=int(round(wage*(1.055**(overall-rating))/500)*500)
        matches.append((max(500,comparable),comp))
    local=[w for w,c in matches if league is not None and c==league]
    peer=local if len(local)>=4 else [w for w,_ in matches]
    return dict(reference=int(round(median(peer)/500)*500) if len(peer)>=4 else None,
                sample=len(peer),local=len(local)>=4)

def market_reference_for_transfer(conn,*,dataset,player_id,club_id):
    """Comparable game wages for players at AI or human clubs."""
    player=conn.execute("""SELECT x.overall,p.primary_position
        FROM world_dataset_ratings x JOIN world_players p
          ON p.player_id=x.player_id
        WHERE x.dataset_id=? AND x.player_id=?""",
        (dataset,player_id)).fetchone()
    if not player or player[0] is None:return None
    return _peer_market_wage(conn,dataset=dataset,club_id=club_id,
        overall=player[0],position=player[1])["reference"]

def wage_signal(conn,*,career_id,player_id):
    target=_target(conn,career_id,player_id)
    peers=_peer_market_wage(conn,dataset=target["dataset"],club_id=target["club"],
        overall=target["overall"],position=target["position"])
    current=target["wage"]
    reference=peers["reference"]
    if reference is None:
        return {**target,**peers,"gap_pct":None,"pressure":0,
                "demand":None,"reason":"Insufficient comparable game wages"}
    gap=max(0,1-current/max(1,reference))
    role=_role_adjustment(target["role"])
    from datetime import date
    expiry=None
    try:expiry=date.fromisoformat(target["expires"]) if target["expires"] else None
    except (ValueError,TypeError):pass
    months=(expiry-date.fromisoformat(target["lock"])).days/30.44 if expiry else None
    horizon=max(0,(24-max(0,months or 24))/24)
    pressure=min(1,gap*.9+horizon*.20+
                 (0.08 if role>=1.05 else 0))
    # The target is not a contractual market fact; it is a bargaining anchor
    # adjusted for team role, expiry and the source comparison.
    demand=max(current+500,int(round(max(current*1.045,
                  reference*role*(1+.06*horizon))/500)*500))
    return {**target,**peers,"gap_pct":round(gap*100,1),
        "pressure":round(pressure,3),"demand":demand,
        "reason":("Wage below comparable game salaries" if gap>=.18
                  else "Seeking improved terms")}

def renewal_info(conn,*,career_id,player_id):
    from world_preseason_window import window_snapshot
    snap=window_snapshot(conn,career_id=career_id)
    if snap["window_id"] is None:return None
    row=conn.execute("""SELECT * FROM world_career_contract_renewals
        WHERE career_id=? AND window_id=? AND player_id=?""",
        (career_id,snap["window_id"],player_id)).fetchone()
    if row is None:return None
    return dict(row)

def all_renewals(conn,*,career_id):
    from world_preseason_window import window_snapshot
    snap=window_snapshot(conn,career_id=career_id)
    if snap["window_id"] is None:return {}
    return {r["player_id"]:dict(r) for r in conn.execute(
        """SELECT * FROM world_career_contract_renewals
           WHERE career_id=? AND window_id=?""",
        (career_id,snap["window_id"])).fetchall()}

def _notify(conn,*,career_id,window_id,player_id,headline,detail,event):
    from world_live_market import _message
    _message(conn,career_id=career_id,window_id=window_id,
        key=f"fc27-renewal:{window_id}:{player_id}:{event}",
        headline=headline,detail=detail)

def generate_player_requests(conn,*,career_id,now=None):
    """Only significant wage/expiry concerns generate incoming player mail.

    Decision is deterministic per career and window; no rerolls or floods.
    """
    from world_preseason_window import window_snapshot
    snap=window_snapshot(conn,career_id=career_id,now=now)
    if snap["state"]!="open":return 0
    car=conn.execute("""SELECT dataset_id,manager_club_id FROM world_career_saves
        WHERE career_id=?""",(career_id,)).fetchone()
    if car is None or car[0]!=DATASET:return 0
    if conn.execute("""SELECT 1 FROM world_career_contract_request_sweeps
        WHERE career_id=? AND window_id=?""",
        (career_id,snap["window_id"])).fetchone():
        return 0
    already=conn.execute("""SELECT COUNT(*) FROM world_career_contract_renewals
        WHERE career_id=? AND window_id=? AND initiated_by='player'""",
        (career_id,snap["window_id"])).fetchone()[0]
    players=conn.execute("""SELECT r.player_id FROM world_career_registrations r
        JOIN world_dataset_ratings x ON x.player_id=r.player_id
             AND x.dataset_id=?
        WHERE r.career_id=? AND r.club_id=?
        ORDER BY x.overall DESC,r.player_id""",
        (DATASET,career_id,car[1])).fetchall()
    candidates=[]
    for (pid,) in players:
        if conn.execute("""SELECT 1 FROM world_career_contract_renewals
            WHERE career_id=? AND window_id=? AND player_id=?""",
            (career_id,snap["window_id"],pid)).fetchone():continue
        try:signal=wage_signal(conn,career_id=career_id,player_id=pid)
        except ValueError:continue
        if signal["demand"] is None:continue
        # Weighted dissatisfaction and contract pressure; an underpaid
        # starter is more likely to ask even with time left on their deal.
        chance=max(0,min(.90,(signal["pressure"]-.14)*1.13))
        if not (signal["gap_pct"]>=40 and
                signal["role"] in ("key_player","regular_starter")) and (
                _stable(career_id,snap["window_id"],pid)>chance):continue
        candidates.append((signal["pressure"],pid,signal))
    candidates.sort(reverse=True)
    count=0
    for _,pid,signal in candidates[:max(0,min(5,5-already))]:
        conn.execute("""INSERT OR IGNORE INTO world_career_contract_renewals
            (career_id,window_id,player_id,club_id,old_weekly_wage,
             peer_weekly_wage,demand_weekly_wage,status,initiated_by,model_version)
            VALUES(?,?,?,?,?,?,?,'requested','player',?)""",
            (career_id,snap["window_id"],pid,signal["club"],signal["wage"],
             signal["reference"],signal["demand"],MODEL))
        _notify(conn,career_id=career_id,window_id=snap["window_id"],
            player_id=pid,event="request",
            headline=signal["name"]+" requests contract talks",
            detail=(f"Current salary £{signal['wage']:,}/week; modelled "
                f"comparable wages £{signal['reference']:,}/week "
                f"({signal['sample']} source peers). "
                "Their agent wants a competitive renewal or may consider a move. "
                "Open Squad → Contract to discuss terms."))
        count+=1
    conn.execute("""INSERT OR IGNORE INTO world_career_contract_request_sweeps
        (career_id,window_id) VALUES(?,?)""",(career_id,snap["window_id"]))
    conn.commit()
    return count

def renewal_action(conn,*,career_id,player_id,action,weekly_wage=None,
                   contract_years=None):
    from world_preseason_window import window_snapshot
    from world_careers import wage_budget_breakdown
    from datetime import date
    snap=window_snapshot(conn,career_id=career_id)
    if snap["state"]!="open":raise ValueError("Renewals require the open 30-minute window")
    target=wage_signal(conn,career_id=career_id,player_id=player_id)
    if target["demand"] is None:
        raise ValueError("Insufficient source wage peers to model negotiations")
    status=renewal_info(conn,career_id=career_id,player_id=player_id)
    if status and status["status"] in ("agreed_future","completed","expired"):
        raise ValueError("This renewal has already been finalised or expired")
    if action not in ("offer","confirm","decline","withdraw"):
        raise ValueError("Unsupported contract decision")
    if action=="offer":
        if type(weekly_wage) is not int or not 0<=weekly_wage<=1_000_000:
            raise ValueError("Enter a valid proposed weekly wage")
        if type(contract_years) is not int or not 1<=contract_years<=5:
            raise ValueError("Contract term must be 1–5 years")
    if action=="confirm" and (not status or status["status"]!="accepted_terms"):
        raise ValueError("Agree terms with the player's agent before confirming")
    if action in ("withdraw","decline") and not status:
        raise ValueError("No ongoing contract discussions")
    if status and status["rounds"]>=6 and action=="offer":
        raise ValueError("Agent negotiations have reached six rounds")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if status is None and action=="offer":
            conn.execute("""INSERT INTO world_career_contract_renewals
                (career_id,window_id,player_id,club_id,old_weekly_wage,
                 peer_weekly_wage,demand_weekly_wage,status,initiated_by,model_version)
                VALUES(?,?,?,?,?,?,?,'negotiating','manager',?)""",
                (career_id,snap["window_id"],player_id,target["club"],target["wage"],
                 target["reference"],target["demand"],MODEL))
        if action=="offer":
            demand=(status["demand_weekly_wage"] if status else target["demand"])
            # Agents weigh length of security too, rather than an artificial
            # same-number acceptance rule for every contract.
            acceptable=demand*(1-.017*max(0,contract_years-2))
            outcome="accepted_terms" if weekly_wage>=acceptable else "countered"
            if weekly_wage<demand*.65 and status and status["rounds"]>=2:
                outcome="declined"
            new_demand=demand if outcome=="accepted_terms" else int(
                round(max(weekly_wage+500,demand*(.992 if contract_years>=3 else 1.0))/500)*500)
            if outcome=="accepted_terms":
                wage=wage_budget_breakdown(conn,career_id,target["club"])
                increment=max(0,weekly_wage-(status["old_weekly_wage"] if status else target["wage"]))
                if increment>wage["remaining"]:
                    raise ValueError("Renewal increase exceeds remaining weekly wage budget")
            conn.execute("""UPDATE world_career_contract_renewals
                SET status=?,offered_weekly_wage=?,contract_years=?,
                    demand_weekly_wage=?,rounds=rounds+1,
                    updated_at=CURRENT_TIMESTAMP
                WHERE career_id=? AND window_id=? AND player_id=?""",
                (outcome,weekly_wage,contract_years,new_demand,
                 career_id,snap["window_id"],player_id))
            message=(f"{target['name']} and agent accepted £{weekly_wage:,}/week "
                f"for {contract_years} years. Confirm the paperwork to make it binding."
                if outcome=="accepted_terms" else
                f"{target['name']}'s agent counters at £{new_demand:,}/week."
                if outcome=="countered" else
                f"{target['name']}'s agent ended contract negotiations.")
            event="offer-"+str((status["rounds"] if status else 0)+1)
        elif action=="confirm":
            diff=max(0,status["offered_weekly_wage"]-status["old_weekly_wage"])
            available=wage_budget_breakdown(conn,career_id,target["club"])["remaining"]
            if diff>available:raise ValueError("Insufficient weekly wage headroom")
            signed_date=datetime.now(timezone.utc).isoformat(timespec="seconds")
            conn.execute("""UPDATE world_career_contract_renewals
                SET status='agreed_future',signed_at=?,updated_at=CURRENT_TIMESTAMP
                WHERE career_id=? AND window_id=? AND player_id=?""",
                (signed_date,career_id,snap["window_id"],player_id))
            message=(f"{target['name']}'s new {status['contract_years']}-year "
                f"contract confirmed at £{status['offered_weekly_wage']:,}/week. "
                f"An extra £{diff:,}/week is reserved for the new season.")
            event="confirmed"
        else:
            result="declined" if action=="decline" else "withdrawn"
            conn.execute("""UPDATE world_career_contract_renewals
                SET status=?,updated_at=CURRENT_TIMESTAMP
                WHERE career_id=? AND window_id=? AND player_id=?""",
                (result,career_id,snap["window_id"],player_id))
            message=(target["name"]+" has been told no new contract is offered."
                if action=="decline" else "Contract negotiations withdrawn.")
            event=result
        _notify(conn,career_id=career_id,window_id=snap["window_id"],
            player_id=player_id,event=event,
            headline="Contract renewal update: "+target["name"],detail=message)
        conn.commit()
        return {"message":message,"status":outcome if action=="offer" else
            "agreed_future" if action=="confirm" else result}
    except Exception:
        conn.rollback()
        raise

def renewal_reserved_delta(conn,*,career_id,club_id):
    if not conn.execute("""SELECT 1 FROM sqlite_master WHERE type='table'
        AND name='world_career_contract_renewals'""").fetchone():
        return 0
    return conn.execute("""SELECT COALESCE(SUM(
        CASE WHEN offered_weekly_wage>old_weekly_wage
             THEN offered_weekly_wage-old_weekly_wage ELSE 0 END),0)
        FROM world_career_contract_renewals
        WHERE career_id=? AND club_id=? AND status='agreed_future'""",
        (career_id,club_id)).fetchone()[0]

def finalise_renewals(conn,*,career_id,effective_date):
    """Run inside the same atomic transaction as deadline registrations."""
    from datetime import date
    closing=date.fromisoformat(effective_date)
    if not conn.execute("""SELECT 1 FROM sqlite_master WHERE type='table'
        AND name='world_career_contract_renewals'""").fetchone():
        return 0
    signed=conn.execute("""SELECT r.window_id,r.player_id,r.club_id,
        r.old_weekly_wage,r.offered_weekly_wage,r.contract_years
        FROM world_career_contract_renewals r
        JOIN world_career_preseason_windows w ON w.window_id=r.window_id
        WHERE r.career_id=? AND r.status='agreed_future'
          AND w.status='open'""",(career_id,)).fetchall()
    count=0
    for wid,pid,club,old,new,years in signed:
        current=conn.execute("""SELECT club_id FROM world_career_registrations
             WHERE career_id=? AND player_id=?""",(career_id,pid)).fetchone()
        if current is None or current[0]!=club:
            # Players who agreed a transfer cannot simultaneously extend
            # their old club's contract: the old renewal is void.
            conn.execute("""UPDATE world_career_contract_renewals
                SET status='withdrawn' WHERE career_id=? AND window_id=? AND player_id=?""",
                (career_id,wid,pid))
            continue
        increment=max(0,new-old)
        ledger=conn.execute("""UPDATE world_career_club_ledger
            SET committed_wages=committed_wages+?
            WHERE career_id=? AND club_id=?
              AND committed_wages+?<=weekly_wage_budget""",
            (increment,career_id,club,increment))
        if ledger.rowcount!=1:raise ValueError("Confirmed renewals exceed wage budget")
        end_year=closing.year+years
        try:expiry=closing.replace(year=end_year)
        except ValueError:expiry=closing.replace(year=end_year,day=28)
        conn.execute("""UPDATE world_career_contract_snapshots
            SET weekly_wage_gbp=?,expires_on=?,renewal_status='agreed',
                source_kind=? WHERE career_id=? AND player_id=?""",
            (new,expiry.isoformat(),MODEL,career_id,pid))
        conn.execute("""UPDATE world_career_player_circumstances
            SET current_wage_weekly=?,renewal_status='renewal_offered'
            WHERE career_id=? AND player_id=?""",(new,career_id,pid))
        conn.execute("""UPDATE world_career_contract_renewals
            SET status='completed',effective_date=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE career_id=? AND window_id=? AND player_id=?""",
            (effective_date,career_id,wid,pid))
        count+=1
    conn.execute("""UPDATE world_career_contract_renewals SET status='expired',
        updated_at=CURRENT_TIMESTAMP WHERE career_id=?
        AND status IN ('requested','negotiating','countered','accepted_terms')""",
        (career_id,))
    return count
