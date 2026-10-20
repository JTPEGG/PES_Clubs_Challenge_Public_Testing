"""Historical league club sporting-appeal regression on isolated CI SQLite.

A real historical career must not reject every offer as 'unassessed' merely
because its competition ID is not ENG1-ENG4. This test only checks whether
simulated personal negotiations may OPEN, not an actual player's consent.
"""
import argparse,json,sqlite3
from world_historical_career_appeal import historical_club_appeal,VERSION
from world_careers import player_move_interest

def verify(path,year):
    db=sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    career=f"historical_{year}_smoke"
    ds=f"pes-v2-{year}-mens-01"
    save=db.execute("""SELECT economy_version FROM world_career_saves
        WHERE career_id=? AND dataset_id=?""",(career,ds)).fetchone()
    if save is None:raise ValueError("Missing original historical smoke career")
    clubs=[(int(cid),int(tier),comp) for cid,tier,comp in db.execute("""
        SELECT e.club_id,c.tier,e.competition_id
        FROM world_dataset_entries e JOIN world_competitions c
        ON c.competition_id=e.competition_id
        WHERE e.dataset_id=? AND c.tier IS NOT NULL
        ORDER BY e.club_id""",(ds,))]
    score={}
    for cid,tier,comp in clubs:
        obj=historical_club_appeal(db,career_id=career,club_id=cid)
        if obj is not None:
            if obj["model"]!=VERSION or obj["source_tier"]!=tier:
                raise ValueError("Source league mapping mismatch")
            score[cid]=obj["score"]
    if len(score)<500:
        raise ValueError("Insufficient source-backed historical sporting appeal")
    choice=None
    for buyer,tier,comp in clubs:
        if buyer not in score:continue
        for seller,other_tier,other_comp in clubs:
            if seller==buyer or comp!=other_comp or seller not in score:continue
            if score[seller]-score[buyer] > 5: continue
            pidrow=db.execute("""SELECT player_id FROM world_career_registrations
                WHERE career_id=? AND club_id=? ORDER BY player_id LIMIT 1""",
                (career,seller)).fetchone()
            if pidrow:
                choice=(buyer,seller,pidrow[0],comp)
                break
        if choice:break
    if choice is None:raise ValueError("No compatible pair of fully source-rated historical clubs")
    buyer,seller,pid,league=choice
    cur=db.execute("""INSERT INTO world_career_offers
        (career_id,request_key,player_id,buying_club_id,selling_club_id,
        offered_fee,status,agreement_date,economy_version)
        VALUES(?,?,?,?,?,?,'proposed',?,?)""",
        (career,f"historical-appeal-regression-{year}",pid,buyer,seller,
         500000,f"{year-1}-07-31",save[0]))
    offer=cur.lastrowid
    # This checks the actual production player-interest entrypoint, which
    # previously used English-only league IDs and always returned 'review'.
    result=player_move_interest(db,career_id=career,offer_id=offer)
    if not result["can_negotiate"] or result["decision"]=="review":
        raise AssertionError(f"Historical league blocker is still active: {result}")
    if not db.execute("""SELECT 1 FROM world_career_contract_snapshots
        WHERE career_id=? AND player_id=?""",(career,pid)).fetchone():
        raise ValueError("Source historical current-wage context not loaded")
    db.rollback()
    print(json.dumps(dict(edition=year,clubs_with_source_backed_game_appeal=len(score),
        total_historical_clubs=len(clubs),buyer=buyer,seller=seller,
        source_competition=league,player_id=pid,
        result=result["decision"],can_open_talks=result["can_negotiate"],
        scope="game-estimated player-interest only; not player consent"),indent=2))
    db.close()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True);p.add_argument("--edition",type=int,required=True)
    a=p.parse_args()
    verify(a.db,a.edition)
