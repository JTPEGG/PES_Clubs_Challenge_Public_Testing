"""Deterministic source-rated squad ranks for FC27-only game simulations."""
from world_ai_bidding import position_family

def fc27_club_player_rank(conn,career_id,player_id,club_id,position,overall):
    rows=conn.execute("""SELECT r.player_id,p.primary_position,x.overall
       FROM world_career_registrations r
       JOIN world_players p ON p.player_id=r.player_id
       JOIN world_career_saves c ON c.career_id=r.career_id
       JOIN world_dataset_ratings x ON x.dataset_id=c.dataset_id
          AND x.player_id=r.player_id
       WHERE r.career_id=? AND r.club_id=? AND x.overall IS NOT NULL
       ORDER BY x.overall DESC,r.player_id""",(career_id,club_id)).fetchall()
    if position_family(position)=="GK":
        rows=[row for row in rows if position_family(row[1])=="GK"]
    for rank,row in enumerate(rows):
        if row[0]==player_id:return rank
    raise ValueError("FC27 rated player must belong to their source club squad")
