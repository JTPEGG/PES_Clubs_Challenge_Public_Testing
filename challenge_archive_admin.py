"""Public read-only archive reads; never migrate, repair, simulate or sync saves."""
import csv
import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, render_template, request


def read_archive(conn, challenge_id=None):
    sql = "SELECT * FROM challenges"
    params = ()
    if challenge_id is not None:
        sql += " WHERE challenge_id=?"
        params = (challenge_id,)
    challenges = conn.execute(sql + " ORDER BY challenge_id", params).fetchall()
    if challenge_id is not None and not challenges:
        abort(404)
    has_playoffs = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='playoff_matches'"
    ).fetchone() is not None
    records = []
    for row in challenges:
        ch = dict(row)
        cid = ch['challenge_id']
        table = [dict(r) for r in conn.execute(
            "SELECT position, team_name, played, won, drawn, lost, goals_for, "
            "goals_against, goal_difference, points FROM league_table "
            "WHERE challenge_id=? ORDER BY position, team_name", (cid,))]
        fixtures = [dict(r) for r in conn.execute(
            "SELECT fixture_id, round, match_no, home_team, away_team, home_goals, "
            "away_goals, played, source FROM fixtures WHERE challenge_id=? "
            "ORDER BY round, match_no", (cid,))]
        playoffs = [dict(r) for r in conn.execute(
            "SELECT playoff_id, stage, leg, match_no, home_team, away_team, "
            "home_goals, away_goals, played, winner_team, source "
            "FROM playoff_matches WHERE challenge_id=? "
            "ORDER BY CASE stage WHEN 'Semi-Final' THEN 1 WHEN 'Final' THEN 2 "
            "ELSE 3 END, match_no, leg, playoff_id", (cid,))] if has_playoffs else []
        final_round = ch.get('final_round')
        final = bool(ch['status'] == 'Completed' and table and fixtures
                     and final_round is not None
                     and all(f['played'] and f['home_goals'] is not None
                             and f['away_goals'] is not None for f in fixtures)
                     and all(r['played'] == final_round for r in table))
        managed = next((r for r in table if r['team_name'] == ch['club_or_nation']), None)
        board = conn.execute(
            "SELECT round, board_confidence, assessment, created_at FROM board_log "
            "WHERE challenge_id=? ORDER BY round DESC, log_id DESC LIMIT 1", (cid,)
        ).fetchone()
        outcomes = {'basis': 'Not confirmed: season incomplete or records missing',
                    'automatic_promotion': None, 'playoff_winner': None,
                    'relegated': None, 'playoff_status': 'Not recorded'}
        if final and ch['competition'] == 'EFL Championship' and len(table) == 24:
            positions = [r['position'] for r in table]
            if len(set(positions)) == len(positions):
                outcomes.update(basis='Calculated from the complete saved Championship table',
                                automatic_promotion=[r['team_name'] for r in table if r['position'] <= 2],
                                relegated=[r['team_name'] for r in table if r['position'] >= 22])
            else:
                outcomes['basis'] = 'Unresolved tied positions in the saved table'
            finals = [r for r in playoffs if r['stage'] == 'Final']
            if len(finals) == 1:
                match = finals[0]
                hg, ag = match['home_goals'], match['away_goals']
                if match['played'] and hg is not None and ag is not None:
                    winner = (match['home_team'] if hg > ag else match['away_team'] if ag > hg
                              else match['winner_team'])
                    eligible = {r['team_name'] for r in table if 3 <= r['position'] <= 6}
                    if winner in {match['home_team'], match['away_team']} and winner in eligible:
                        outcomes['playoff_winner'] = winner
                        outcomes['playoff_status'] = 'Recorded final result'
        records.append({
            'challenge': {k: ch.get(k) for k in ('challenge_id', 'club_or_nation', 'competition',
                'objective', 'status', 'start_round', 'final_round', 'opening_position',
                'opening_points', 'target_position')},
            'table_is_final': final, 'managed_table_row': managed,
            'league_table': table, 'outcomes': outcomes,
            'latest_recorded_board_assessment': dict(board) if board else None,
            'fixtures': fixtures, 'playoffs': playoffs,
        })
    return {'generated_at': datetime.now(timezone.utc).isoformat(),
            'source': 'Application working save; no starter-data fallback', 'challenges': records}


def create_archive_blueprint(database_path):
    bp = Blueprint('challenge_archive_admin', __name__, url_prefix='/admin/challenge-archive')

    @bp.after_request
    def archive_response(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    def snapshot():
        try:
            # mode=ro refuses to create a missing DB; a transaction keeps all queries consistent.
            conn = sqlite3.connect(Path(database_path).resolve().as_uri() + '?mode=ro', uri=True)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute('PRAGMA query_only=ON')
                conn.execute('BEGIN')
                return read_archive(conn, request.args.get('challenge_id'))
            finally:
                conn.close()
        except sqlite3.Error:
            abort(503, description='Saved archive data is unavailable. No fallback results were substituted.')

    @bp.route('')
    @bp.route('/')
    def index():
        return render_template('admin_challenge_archive.html', archive=snapshot())

    @bp.route('/export.json')
    def export_json():
        response = jsonify(snapshot())
        response.headers['Content-Disposition'] = 'attachment; filename="challenge-archive.json"'
        return response

    @bp.route('/export.csv')
    def export_csv():
        data = snapshot()
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['challenge_id', 'club', 'status', 'record_type', 'table_is_final',
                         'position', 'team', 'played', 'won', 'drawn', 'lost', 'gf', 'ga', 'gd', 'points',
                         'round_or_stage', 'home', 'away', 'home_goals', 'away_goals', 'outcome_or_objective'])
        def safe(value):
            # Prevent spreadsheet formula execution from team names or recorded text.
            return "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value
        for item in data['challenges']:
            ch = item['challenge']
            prefix = [ch['challenge_id'], ch['club_or_nation'], ch['status']]
            rows = [[*prefix, 'challenge', item['table_is_final'], *([''] * 15), ch['objective']]]
            for r in item['league_table']:
                rows.append([*prefix, 'table', item['table_is_final'], *[r[k] for k in
                    ('position','team_name','played','won','drawn','lost','goals_for','goals_against','goal_difference','points')], *([''] * 6)])
            for kind, matches in [('fixture', item['fixtures']), ('playoff', item['playoffs'])]:
                for r in matches:
                    rows.append([*prefix, kind, item['table_is_final'], '', '', r['played'], *([''] * 7),
                                 r.get('round', r.get('stage')), r['home_team'], r['away_team'],
                                 r['home_goals'], r['away_goals'], r.get('winner_team', '')])
            for key in ('automatic_promotion', 'playoff_winner', 'relegated'):
                value = item['outcomes'][key]
                text = '; '.join(value) if isinstance(value, list) else value or 'Not confirmed / not recorded'
                rows.append([*prefix, key, item['table_is_final'], *([''] * 15), text])
            board = item['latest_recorded_board_assessment']
            if board:
                rows.append([*prefix, 'recorded_board_assessment', item['table_is_final'], *([''] * 15), board['assessment']])
            writer.writerows([[safe(v) for v in row] for row in rows])
        return Response(output.getvalue(), mimetype='text/csv', headers={
            'Content-Disposition': 'attachment; filename="challenge-archive.csv"'})

    return bp
