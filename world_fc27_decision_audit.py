"""Source-backed FC27 market funnel diagnostics (no behavioural overrides).

Keep independent club intent, scouting choices and failed negotiations visible.
This information is GAME SIMULATION, not real-world club or player intentions.
No country weighting, transfer cap or scouting chance is changed by the audit.
"""
from collections import Counter

SCHEMA="""
CREATE TABLE IF NOT EXISTS world_fc27_market_club_evaluations(
  window_id INTEGER NOT NULL,
  interval_index INTEGER NOT NULL,
  club_id INTEGER NOT NULL,
  source_priority REAL,
  scout_draw INTEGER,
  commitment_draw INTEGER,
  stage TEXT NOT NULL,
  PRIMARY KEY(window_id,interval_index,club_id)
);
CREATE INDEX IF NOT EXISTS world_fc27_eval_window_stage
 ON world_fc27_market_club_evaluations(window_id,stage);
CREATE TABLE IF NOT EXISTS world_fc27_market_negotiation_diagnostics(
  window_id INTEGER NOT NULL,
  interval_index INTEGER NOT NULL,
  club_id INTEGER NOT NULL,
  search_family TEXT,
  search_strategy TEXT,
  eligible_candidates INTEGER DEFAULT 0,
  same_country_candidates INTEGER DEFAULT 0,
  foreign_country_candidates INTEGER DEFAULT 0,
  affordable_same_country INTEGER DEFAULT 0,
  affordable_foreign_country INTEGER DEFAULT 0,
  first_eligible_player_id INTEGER,
  first_eligible_seller_id INTEGER,
  first_eligible_source_country TEXT,
  chosen_player_id INTEGER,
  chosen_seller_id INTEGER,
  selected_source_country TEXT,
  result_stage TEXT NOT NULL,
  reason TEXT,
  PRIMARY KEY(window_id,interval_index,club_id)
);
"""

def initialize_decision_audit(conn):
    conn.executescript(SCHEMA)
    conn.commit()

def save_evaluations(conn,rows):
    conn.executemany("""INSERT OR IGNORE INTO world_fc27_market_club_evaluations
      (window_id,interval_index,club_id,source_priority,scout_draw,
       commitment_draw,stage)
      VALUES(?,?,?,?,?,?,?)""",rows)

def save_negotiation(conn,*,window_id,interval_index,club_id,**facts):
    """One row per independent intent, updated at each substantive decision.

    Avoid storing inferred motivations: status comes from actual execution,
    and selected country comes from the source club's competition.
    """
    allowed={
        "search_family","search_strategy","eligible_candidates",
        "same_country_candidates","foreign_country_candidates",
        "affordable_same_country","affordable_foreign_country",
        "first_eligible_player_id","first_eligible_seller_id",
        "first_eligible_source_country","chosen_player_id",
        "chosen_seller_id","selected_source_country","result_stage","reason"
    }
    if not facts or set(facts)-allowed or "result_stage" not in facts:
        raise ValueError("Source-backed negotiation stage required")
    conn.execute("""INSERT OR IGNORE INTO
      world_fc27_market_negotiation_diagnostics
      (window_id,interval_index,club_id,result_stage)
      VALUES(?,?,?,'not_processed')""",(window_id,interval_index,club_id))
    # Updating only supplied fields preserves ranked shortlist provenance.
    columns=list(facts)
    conn.execute("""UPDATE world_fc27_market_negotiation_diagnostics SET
      """+", ".join(f"{column}=?" for column in columns)+"""
      WHERE window_id=? AND interval_index=? AND club_id=?""",
      tuple(facts.values())+(window_id,interval_index,club_id))
    conn.commit()

def source_club_countries(conn,dataset):
    return dict(conn.execute("""SELECT e.club_id,c.country
      FROM world_dataset_entries e JOIN world_competitions c
        ON c.competition_id=e.competition_id
      WHERE e.dataset_id=?""",(dataset,)))

def shortlist_country_mix(*,options,buyer,countries):
    """Country mix among *ranked eligible* candidates, without any bias.

    options: (seller_id,player_id,...) from the actual FC27 shortlist.
    Unknown countries are kept unknown, not guessed as domestic/foreign.
    """
    home=countries.get(buyer)
    counts=Counter()
    for option in options:
        source=countries.get(option[0])
        label=("unknown" if source is None or home is None else
               "same_country" if source==home else "foreign")
        counts[label]+=1
    return {"same_country_candidates":counts["same_country"],
            "foreign_country_candidates":counts["foreign"],
            "unknown_country_candidates":counts["unknown"]}
