"""Deterministic FC27 squad depth estimates for game decisions and UI.

Squad roles are *game estimates* based on source ratings, not official
real-world promises. The same ranking policy is used when the live
30-minute window seeds its snapshot. Player-issued role instructions override
these estimates rather than being silently reset.
"""
from world_ai_bidding import position_family


def _club_rating_rows(conn,career_id,club_id):
    return conn.execute("""SELECT r.player_id,p.primary_position,x.overall
       FROM world_career_registrations r
       JOIN world_players p ON p.player_id=r.player_id
       JOIN world_career_saves c ON c.career_id=r.career_id
       JOIN world_dataset_ratings x ON x.dataset_id=c.dataset_id
          AND x.player_id=r.player_id
       WHERE r.career_id=? AND r.club_id=? AND x.overall IS NOT NULL
       ORDER BY x.overall DESC,r.player_id""",(career_id,club_id)).fetchall()


def fc27_club_player_rank(conn,career_id,player_id,club_id,position,overall):
    rows=_club_rating_rows(conn,career_id,club_id)
    if position_family(position)=="GK":
        rows=[row for row in rows if position_family(row[1])=="GK"]
    for rank,row in enumerate(rows):
        if row[0]==player_id:return rank
    raise ValueError("FC27 rated player must belong to their source club squad")


def fc27_source_squad_role(conn,career_id,player_id,club_id):
    """Match real live-market seed ranks, including GK positional depth.

    Most valuable three squad players are key players; ranks 4-11 regular,
    12-18 rotation, others fringe. Goalkeepers are compared only with GKs
    for a starting place; first GK is key iff in squad-wide top three.
    """
    rows=_club_rating_rows(conn,career_id,club_id)
    goalie_rank=0
    for rank,(pid,position,overall) in enumerate(rows):
        if position_family(position)=="GK":
            role=("key_player" if goalie_rank==0 and rank<3 else
                  "regular_starter" if goalie_rank==0 else
                  "rotation" if goalie_rank==1 else "fringe")
            goalie_rank+=1
        else:
            role=("key_player" if rank<3 else "regular_starter"
                  if rank<11 else "rotation" if rank<18 else "fringe")
        if pid==player_id:return role
    raise ValueError("FC27 source player not in the club's rated squad")
