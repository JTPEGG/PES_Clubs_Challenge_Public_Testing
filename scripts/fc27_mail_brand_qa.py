"""Fast regression for club identity and immutable transfer correspondence."""
import sqlite3
from world_career_branding import club_brand
from world_career_correspondence import correspondence

def run():
    burnley=club_brand("Burnley [WH27:abcdef1234]")
    assert burnley["name"]=="Burnley"
    assert burnley["logo"] and "328.png" in burnley["logo"]
    assert burnley["primary"]=="#6C1D45"
    assert club_brand("Unmapped FC27 Club")["logo"] is None
    assert club_brand("Unmapped FC27 Club")["initials"]=="UFC"

    messages=[
        dict(message_id=1,message_key="manager-bid:2",offer_id=2,player_id=7,
            player_name="Player A",buyer_name="Burnley",seller_name="Everton",
            buying_club_id=1,selling_club_id=5,offered_fee=2000000,demanded_fee=None,
            detail="Manager bid submitted",headline="Your bid was sent",
            created_at="2026-11-11T15:00:00+00:00",is_read=1),
        dict(message_id=2,message_key="manager-buy-review:2",offer_id=2,player_id=7,
            player_name="Player A",buyer_name="Burnley",seller_name="Everton",
            buying_club_id=1,selling_club_id=5,offered_fee=2000000,demanded_fee=3850000,
            detail="Seller countered",headline="Everton want £3.85m for Player A",
            created_at="2026-11-11T15:01:00+00:00",is_read=0)
    ]
    letters=correspondence(messages,1)
    assert len(letters)==2
    assert letters[0]["subject"].startswith("Everton counter")
    assert "£3.85m" in letters[0]["body"]
    assert all(x["stage"]!=5 for x in letters)
    assert correspondence(messages,99)==[]

    db=sqlite3.connect(":memory:")
    db.executescript("""
       CREATE TABLE world_players(player_id INTEGER PRIMARY KEY,full_name TEXT);
       CREATE TABLE world_career_contract_renewals(career_id TEXT,player_id INTEGER);
       CREATE TABLE world_fc27_free_agent_offers(
           signing_id INTEGER PRIMARY KEY,career_id TEXT,player_id INTEGER,
           proposed_weekly_wage_gbp INTEGER,contract_years INTEGER);
       CREATE TABLE world_fc27_free_agent_events(
           event_id INTEGER,signing_id INTEGER,event TEXT,detail TEXT,recorded_at TEXT);
       INSERT INTO world_players VALUES(7,'Player A'),(8,'Player B'),(9,'Player C');
       INSERT INTO world_career_contract_renewals VALUES('QA',8);
       INSERT INTO world_fc27_free_agent_offers VALUES(5,'QA',9,17500,3);
       INSERT INTO world_fc27_free_agent_events VALUES(
           4,5,'agent_response','Agent has agreed provisional contract terms',
           '2026-11-11 15:03:00');
       INSERT INTO world_fc27_free_agent_events VALUES(
           5,5,'manager_confirmed','Manager signed',
           '2026-11-11 15:04:00');
    """)
    messages.append(dict(message_id=3,message_key="fc27-renewal:1:8:confirmed",
        offer_id=None,player_id=None,headline="Contract renewal update: Player B",
        detail="Player B signed a new contract",created_at="2026-11-11T15:02:00+00:00",
        is_read=0))
    messages.append(dict(message_id=4,
        message_key="player-review-outcome:free_agent:5",offer_id=None,
        player_id=None,headline="Player accepts your contract",
        detail="Player accepts",created_at="2026-11-11T15:03:30+00:00",
        is_read=0))
    letters=correspondence(messages,1,conn=db,career_id="QA")
    assert any(x["subject"]=="New contract signed: Player B" for x in letters)
    assert any(x["subject"]=="Player C accepts our contract" for x in letters)
    assert any(x["subject"]=="Free-agent signing confirmed: Player C" for x in letters)
    assert any(x["message_id"]=="fa-5" for x in letters)
    print("Manager correspondence and club branding QA passed")

if __name__=="__main__":
    run()
