"""Persisted post-window PES squad preparation checklist for development careers.

This checklist never changes career registrations or claims to have exported
a console option file. The manager must apply transfers to PES outside the app.
"""
from world_preseason_window import window_snapshot

_STEPS=("review","apply_pes","verify_squads")

_SCHEMA="""
CREATE TABLE IF NOT EXISTS world_career_season_setup(
 career_id TEXT NOT NULL REFERENCES world_career_saves(career_id),
 window_id INTEGER NOT NULL REFERENCES world_career_preseason_windows(window_id),
 step TEXT NOT NULL CHECK(step IN ('review','apply_pes','verify_squads')),
 done INTEGER NOT NULL CHECK(done IN (0,1)),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(career_id,window_id,step)
);
"""


def checklist(conn,*,career_id):
    snap=window_snapshot(conn,career_id=career_id)
    if snap["state"]!="closed":
        return {"available":False,"steps":{},"completed":False}
    conn.executescript(_SCHEMA)
    rows=conn.execute("""SELECT step,done FROM world_career_season_setup
        WHERE career_id=? AND window_id=?""",
        (career_id,snap["window_id"])).fetchall()
    steps={step:bool(dict(rows).get(step,0)) for step in _STEPS}
    return {"available":True,"steps":steps,
            "completed":all(steps.values()),"window_id":snap["window_id"]}


def change_step(conn,*,career_id,step,done):
    if step not in _STEPS or type(done) is not bool:
        raise ValueError("Select a valid season preparation task")
    snap=window_snapshot(conn,career_id=career_id)
    if snap["state"]!="closed":
        raise ValueError("Season setup is available only after the transfer window closes")
    conn.executescript(_SCHEMA)
    conn.execute("""INSERT INTO world_career_season_setup
        (career_id,window_id,step,done)
        VALUES(?,?,?,?)
        ON CONFLICT(career_id,window_id,step)
        DO UPDATE SET done=excluded.done,updated_at=CURRENT_TIMESTAMP""",
        (career_id,snap["window_id"],step,int(done)))
    conn.commit()
    return checklist(conn,career_id=career_id)
