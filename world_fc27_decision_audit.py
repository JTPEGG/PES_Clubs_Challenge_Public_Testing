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
  contract_phase TEXT,
  offer_id INTEGER,
  source_reference_fee_gbp INTEGER,
  buyer_offer_fee_gbp INTEGER,
  seller_counter_fee_gbp INTEGER,
  buyer_sensible_ceiling_gbp INTEGER,
  promised_role TEXT,
  player_interest_signal TEXT,
  player_required_role TEXT,
  source_player_wage_gbp INTEGER,
  agent_initial_demand_gbp INTEGER,
  agent_final_demand_gbp INTEGER,
  buyer_remaining_wage_gbp INTEGER,
  result_stage TEXT NOT NULL,
  reason TEXT,
  PRIMARY KEY(window_id,interval_index,club_id)
);
"""

DETAIL_COLUMNS={
    "contract_phase":"TEXT",
    "offer_id":"INTEGER",
    "source_reference_fee_gbp":"INTEGER",
    "buyer_offer_fee_gbp":"INTEGER",
    "seller_counter_fee_gbp":"INTEGER",
    "buyer_sensible_ceiling_gbp":"INTEGER",
    "promised_role":"TEXT",
    "player_interest_signal":"TEXT",
    "player_required_role":"TEXT",
    "source_player_wage_gbp":"INTEGER",
    "agent_initial_demand_gbp":"INTEGER",
    "agent_final_demand_gbp":"INTEGER",
    "buyer_remaining_wage_gbp":"INTEGER",
}

def classify_negotiation_failure(phase,exception):
    """Separate genuine agent/player refusals from model errors.

    Do not erase the actual exception or invent consent. Classification is
    diagnostic only; the signing engine still retains its original policies.
    """
    if phase=="agent_quote" and "Player will not open agent talks" in str(exception):
        return "player_refused_agent_talks"
    if phase in ("agent_first_response","agent_counter_response"):
        return "agent_negotiation_failure"
    if phase in ("player_interest",):
        return "player_interest_evaluation_failure"
    if phase in ("seller_model","buyer_pricing","seller_response","offer_submission"):
        return "seller_or_offer_evaluation_failure"
    return "negotiation_processing_error"


def initialize_decision_audit(conn):
    conn.executescript(SCHEMA)
    # Upgrade only isolated development audit tables if a previous sandbox
    # was already created. No live or legacy career table is touched.
    existing={row[1] for row in conn.execute(
        "PRAGMA table_info(world_fc27_market_negotiation_diagnostics)")}
    for name,kind in DETAIL_COLUMNS.items():
        if name not in existing:
            conn.execute("ALTER TABLE world_fc27_market_negotiation_diagnostics "
                         f"ADD COLUMN {name} {kind}")
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
        "chosen_seller_id","selected_source_country","result_stage","reason",
        *DETAIL_COLUMNS
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
