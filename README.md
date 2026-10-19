> **Development Career Mode design contract:** [Autonomous career world — Manager's Inbox, no manual circumstances, dynamic transfer market](docs/AUTONOMOUS_CAREER_WORLD_DESIGN.md). Approved design direction; not yet implemented. Production challenge remains unchanged.

# PES Manager Career Web App v9 — Mobile Page Split

Built on v8 BBC Sport-style.

New in v9:
- Mobile-first horizontal navigation.
- Split dashboard into separate pages:
  - `/table` — League Table
  - `/around` — Around the Grounds
  - `/manager` — Manager Dashboard
  - `/players` — Player Stats
  - `/results` — Results with scorers and assisters
- Dashboard homepage is now a lighter challenge hub.
- Human Players renamed to Player Stats.
- Results page includes:
  - match score
  - scorers
  - assisters
  - per-player goals/assists/cards/ratings
- League table now identifies:
  - automatic promotion places
  - play-off places
  - relegation zone
- Styling remains BBC Sport-inspired.

Deploy:
1. Unzip this folder.
2. Upload/replace the files in GitHub.
3. Commit changes.
4. Render redeploys automatically, or use Manual Deploy -> Deploy latest commit.

Important upload check:
- `app.py` must start with Python: `from flask import...`
- `requirements.txt` must only contain Flask and gunicorn.
- HTML files must live inside `templates/`.

v10 update:
- Results page redesigned.
- Club logos and names now dominate each result card.
- Scoreline moved into a stronger central display.
- Player-controlled team is highlighted.
- Goal scorers shown as football icon chips.
- Assisters shown as green A icon chips.
- Detailed player stats moved into an expandable section.

v10.1 update:
- Results page made more compact.
- Match rows now flow like the Around the Grounds scores, just slightly larger.
- Removed the separate Player-controlled team / Derby County contributions header.
- Removed Scorers and Assisters section titles.
- Goal and assist chips now sit directly underneath the player-controlled team only.
- Football chips show scorers; green A chips show assisters.

v11 update:
- Header title changed from PES Manager Career to Pro Clubs.
- Current managed-team Results page is now called Matches.
- Matches page now includes upcoming fixtures and completed matches.
- Around page is now labelled Results.
- Jobs are locked while the current challenge is still active.
- League table now lightly shades automatic promotion and play-off places.
- Relegation shading remains.
- Career page heading changed from Career Human Player Totals to Player Stats.

v12 update:
- Home page competition title made much bigger.
- Competition logo handling corrected with a guaranteed local EFL Championship fallback.
- Players navigation label changed to Stats.
- Removed the Human Player Tracker title above the stats table.
- Matches page contribution chips are now seamless rather than boxed.
- Match contribution names use surnames/second names where available.
- Completed matches are ordered latest first.

v13 update:
- Home page competition header cleaned up.
- Removed repeated Championship wording from inside the logo asset.
- Local competition mark now shows as a standalone blue dot logo.
- Competition title now displays once, much larger, beside the logo.
- Championship competitions display as EFL Championship even if the database value is just Championship.

v14 update:
- Added Save Protection tools:
  - `/admin/backup`
  - `/export-save`
  - `/import-save`
- Export downloads the live SQLite save file.
- Import restores a previously exported .db save.
- App now supports `DATABASE_PATH` environment variable for future persistent disk setup.
- Added Challenge Complete screen:
  - `/challenge-complete`
  - final position
  - final points
  - Jake's record
  - board verdict
  - top scorers
  - top assisters
  - job unlock action
- Jobs can be unlocked by completing the challenge once all managed fixtures are posted.

v14.1 update:
- Fixed crash after marking a challenge as Completed.
- Home, Table, Results, Stats, Manager and Matches now display the latest completed challenge when no active challenge exists.
- Jobs still unlock once there is no active challenge.
- Post Result is protected from posting new results to a completed challenge.

v14.2 update:
- Home page detects when games left is 0 and shows a clear Challenge Complete banner.
- Home page now shows Objective Exceeded, Objective Met or Objective Failed.
- Board card no longer says the challenge is still alive when all games are complete.
- Final board message includes final position and final points.

v14.3 update:
- Hardened the Start New Challenge / accept job offer flow.
- Prevents Internal Server Error when a new challenge cannot be created.
- Uses the most recent completed challenge as the source scenario.
- Cleans up partial CH002 retry data before recreating the next challenge.
- Normalises offer positions like "11th" into numeric opening positions.
- Adds `/admin/job-debug` to inspect challenges, offers and available teams.

v14.4 update:
- Board verdicts rewritten to sound like a proper assessment rather than a restatement of final position and points.
- Verdict now considers:
  - objective type
  - starting position
  - final position
  - points gained
  - Jake's win/draw/loss record
  - points per game
  - whether the run-in showed progress or failure
- Home completion message also now uses a more nuanced outcome description.

v14.5 update:
- Fixed new challenge creation foreign-key failures.
- New challenge creation now ensures the Jake Brown manager row exists before inserting CH002.
- It also ensures every team used by the cloned table and fixtures exists in the teams master table.
- Partial CH002 attempts are now cleaned more safely, including stricter databases with foreign keys.
- `/admin/job-debug` now includes a SQLite foreign-key check summary.

v14.6 update:
- Board assessment now checks whether the objective is mathematically possible.
- If the team is 5 points off the target with 1 game left, it now says the objective is impossible rather than alive.
- Board confidence is capped down when the objective becomes impossible.
- Home and Manager pages also override stale board text if the live table makes the objective impossible.

v14.7 update:
- Fixed Jobs page Internal Server Error after a challenge is completed.
- Jobs route now defines and passes `fk_issues` properly.
- Job Debug page now receives foreign-key status correctly.
- Jobs page now shows a small admin foreign-key status block instead of crashing.

v14.8 update:
- Fixed the Jobs page crash after completing a challenge.
- Jobs route now always defines `fk_issues` before rendering the Jobs template.
- Added a Jobs error page instead of a raw Internal Server Error if anything unexpected occurs.
- Challenge Complete confirmation is now idempotent: clicking it again after completion redirects to Jobs instead of erroring.
- Job Debug now receives and displays the foreign-key status correctly.

v14.9 update:
- Softened the Home competition header: smaller title, less heavy weight, less aggressive spacing.
- Competition logos now use a local-first / football-logos.cc fallback system.
- EFL Championship now resolves to the football-logos.cc Championship crest instead of the old placeholder mark.
- Added common competition logo aliases and remote sources for Premier League, EFL Championship, EFL League One, EFL League Two, UEFA Champions League, UEFA Europa League, UEFA Conference League, La Liga, Serie A, Bundesliga and Ligue 1.
- Added `static/competition_logos/competition_logo_sources.json` as the source manifest.
- Added `scripts/download_competition_logos.py` so hard-copy local backups can be downloaded into `static/competition_logos` later.

v15 update:
- Added Premier League 2019/20 as a startable competition template.
- Added Premier League job offers: Manchester United, Arsenal, Tottenham Hotspur, Everton, Aston Villa and West Ham United.
- Premier League challenge creation no longer clones the Championship table; it uses a dedicated 20-team Premier League 2019/20 run-in template.
- Added opening table after 30 games, rounds 31-38 fixtures, Premier League survival/top-half/Europe/Champions League objective targets, and team-strength values for computer simulation.
- Added Premier League team crest URL fallbacks for 2019/20 teams not already covered.
- Existing live saves will seed the new Premier League offers automatically on first app load after deploy.

v16 update:
- Reset packaged database back to a fresh Derby County CH001 challenge.
- Added `/admin/reset-derby` to reset the live database back to tonight's Derby run-in.
- Added `/admin/fixture-order` to reorder Derby's PES fixture order after a custom league generates a schedule.
- Fresh Derby setup:
  - Derby County
  - EFL Championship
  - starts after 38 games
  - 10th place
  - 61 points
  - target position: 6th
  - no posted results
- Fixture editor can change Derby's home/away and opponent order before results are posted.

v16.1 update:
- Removed admin tools from the main navigation:
  - Debug
  - Reset
  - Backup
  - Fixtures
- Renamed the fixture-order admin page to Fixture Admin.
- Admin tools remain available by direct URL only:
  - `/admin/backup`
  - `/admin/reset-derby`
  - `/admin/fixture-order`
  - `/admin/job-debug`

v16.2 update:
- Fixed Matches page Internal Server Error by restoring the managed results helper.
- Fixed Results page Internal Server Error by restoring the all played rounds helper.
- Fixed upcoming Matches helper.
- Complete page is now contextual:
  - before any games, it shows a pre-challenge board progress check
  - during the run-in, it shows an in-progress board update
  - only after all games are posted does it show a final board verdict
- Matches details table now matches the actual save schema and no longer expects card/rating fields that are not stored.

v16.3 update:
- Added Fixture Admin validation.
- Duplicate Derby opponents are now blocked server-side and client-side.
- Fixture Admin now uses the original Derby run-in opponent list rather than the currently saved fixture list.
- This means a bad saved order, such as Cardiff appearing twice and Sunderland missing, can be corrected without resetting the whole challenge.
- Save button disables automatically when duplicate opponents are selected.

v16.4 update:
- Reordered visible navigation to:
  Home, Table, Matches, Results, Stats, Career, Post, Complete, Jobs.
- Admin tools remain hidden from the main navigation and accessible by direct URL only.

v16.5 update:
- Changed the top-bar title from Pro Clubs to Clubs Challenge.

v16.6 update:
- Added Tim Rees as a human player.
- Tim Rees is included in the packaged database.
- Derby reset now keeps/recreates Tim Rees so he remains available for tonight's challenge.

v16.7 update:
- Upgraded the website background score simulation engine.
- The managed PES result remains exactly as entered.
- Around-the-grounds/background fixtures now use:
  - attack rating
  - defence rating
  - hidden team strength
  - home advantage
  - live league position
  - live goal difference
  - Poisson-style goal sampling
- This should produce more varied and believable results than the previous fixed scoreline model.

v16.8 update:
- Added cached PESMaster PES 2020 team ratings for the simulation engine.
- Team table now uses PESMaster-style:
  - Overall -> hidden_strength
  - Attack -> attack
  - Defence -> defence
- Added `team_rating_sources` table for transparency.
- Added `/admin/team-ratings` hidden admin page.
- Added `/admin/team-ratings/apply` to re-apply cached ratings after importing an older save.
- Added `/static/data/team_ratings_pesmaster_2020.json`.
- Teams not in PES 2020 English 2nd Division use clearly-labelled challenge fallbacks.

v17 update:
- Rebuilt CH001 around the PES 2020 English 2nd Division / 2019-20 Championship team set.
- Removed modern hybrid clubs:
  Burnley, Sheffield United, Norwich City, Coventry City, Sunderland, Watford, Plymouth Argyle, Oxford United, Portsmouth, Rotherham United.
- Added the correct PES 2020 Championship clubs:
  Barnsley, Birmingham City, Brentford, Charlton Athletic, Fulham, Huddersfield Town, Nottingham Forest, Reading, Sheffield Wednesday, Wigan Athletic.
- Reset Derby challenge to the real 2019/20 matchday-38 table:
  Derby County start 12th on 54 points, target top six.
- Derby run-in now uses PES 2020-compatible opponents:
  Reading, Preston North End, Nottingham Forest, West Bromwich Albion, Brentford, Cardiff City, Leeds United, Birmingham City.
- All 24 teams have cached PESMaster PES 2020 ratings.
- No challenge fallback team ratings remain in the Championship scenario.

v17.1 update:
- Restored the previous styled navigation bar formatting.
- Navigation order remains:
  Home, Table, Matches, Results, Stats, Career, Post, Complete, Jobs.
- Admin tools remain hidden from the main nav.

v17.2 update:
- Restored Tim Rees as a human player after the v17 PES 2020 rebuild.
- Tim Rees is included in the packaged database.
- `/admin/reset-derby` now keeps Tim Rees available.
- Post Result now ensures the current human-player roster exists before loading the player list.
- Added hidden helper route `/admin/human-players/apply` to update older live saves without a full reset.

v17.3 update:
- Removed developer-facing "PES 2020-aligned" wording from the board confidence message.
- Opening board text now stays in-universe:
  "Derby challenge started. Derby begin 12th on 54 points, three points outside the play-offs."

v17.4 update:
- Added/expanded club crest mapping so all current PES 2020 Championship teams in CH001 have logos.
- Added logo aliases for:
  - Preston -> Preston North End
  - West Brom -> West Bromwich Albion
  - Nottm Forest -> Nottingham Forest
  - Sheff Wed -> Sheffield Wednesday
- This is a visual-only update and does not require a Derby challenge reset.

v17.5 update:
- Restored Tim Rees as a human player on top of the v17.4 logo fix.
- Tim Rees is included in the packaged database.
- Post Result now ensures Tim Rees exists before loading the posting form.
- `/admin/reset-derby` now keeps/recreates Tim Rees.
- Added hidden repair route `/admin/human-players/apply`.

v17.6 update:
- Fixed Tim Rees not appearing in the Post Result page.
- The Post page uses the `HUMAN_PLAYERS` constant, so Tim Rees has now been added there directly.
- Tim Rees is also in the packaged database and the live-save repair route.
- Added `/admin/human-players/apply` as a direct repair route.
- Fixed Birmingham City badge issue by removing the bad Leicester crest mapping and adding a local Birmingham fallback badge.
- Visual/player-list fix only; no Derby reset required unless your live save is still on the old non-PES-2020 dataset.

v17.7 update:
- Removed the Table tab explanatory line about automatic promotion/play-off/relegation zones.
- Hid Jobs from the main navigation for now.
- Post Result now supports player role:
  Started, Came on as sub, Did not play.
- Added `started` and `substitute` columns to player_match_events, with live migration.
- Stats pages now display apps as starts (sub apps), e.g. 6 (3).
- Added team-logo match header to the Post tab.
- Added local fallback badges for Birmingham City, Barnsley and Charlton Athletic so they no longer pull incorrect remote crests.

v17.8 update:
- Replaced placeholder/problem badges for Barnsley, Birmingham City and Charlton Athletic with direct SVG image asset URLs.
- Removed local placeholder SVG files for those three teams so they cannot override the real badges.
- Added remote-priority handling for those three clubs in logo_for_team().
- No Derby reset required.

v17.9 update:
- Corrected distorted logo proportions for Barnsley, Birmingham City and Charlton Athletic.
- The real remote SVG logo files remain in use.
- Added CSS rules to preserve intrinsic aspect ratio instead of squeezing badges into a fixed square.
- Removed any remaining local placeholder SVGs for those three clubs.
- No Derby reset required.

v18 update:
- Added Play-Off Mode.
- New `/playoffs` page.
- If Derby finish 3rd-6th, the app can generate Championship play-off semi-finals:
  - 3rd v 6th
  - 4th v 5th
  - two-legged semi-finals
  - final generated after both semi-finals are complete
- New `/playoffs/post/<playoff_id>` result entry page.
- Derby play-off matches support human goals, assists, starts, substitute appearances, cards and ratings.
- Tied aggregate/final scores allow a selected winner after extra time/penalties.
- Challenge Complete now waits for the play-off campaign to finish before giving the final board verdict.
- Home page will show play-off qualification instead of prematurely closing the challenge.

v18.1 update:
- Fixed the Table tab layout after the logo proportion changes.
- Restored a fixed-width, proper table-cell layout for the league table.
- Club badges are now constrained to 24x24 inside the table only.
- Keeps v18 Play-Off Mode, Tim Rees, starts/subs, hidden Jobs and logo fixes.

v18.2 update:
- Fixed the league table play-off zone rows collapsing/misaligned.
- Scoped new Play-Off Mode CSS to `.playoffs-page` so it cannot affect league table rows.
- Removed the flex override from the club-name table cell.
- Re-applied normal table-row/table-cell display to all league table rows.
- Keeps v18 Play-Off Mode and v18.1 fixes.

v18.3 update:
- Restored the blue shaded background for the league-table play-off zone.
- Rows 3rd to 6th are blue again.
- This is a colour-only fix and does not touch the table layout.
- Keeps v18 Play-Off Mode and all v18.2 table layout fixes.

v18.4 update:
- Fixed league-table zone colours using explicit row classes instead of nth-child counting.
- Automatic promotion rows 1-2 are green.
- Play-off rows 3-6 are blue.
- Relegation rows are red.
- Derby/current team remains yellow as the stronger highlight.
- Fixed crest/name vertical alignment in shaded table rows.

v18.5 update:
- Fixed full league-table row alignment, not just shaded rows.
- Removed remaining table-cell flex conflicts.
- Applied one consistent row height, padding and vertical alignment to every league table row.
- Kept explicit row-class colouring:
  - automatic promotion green
  - play-offs blue
  - relegation red
  - Derby/current team yellow

v18.7 update:
- Improved the Career tab challenge timeline card.
- Added managed-club GF, GA and GD.
- Changed record display to W-D-L format.
- Replaced the awkward loose record line with a proper run-in record panel.
- Includes regular-season results and played play-off matches where present.
- Kept Career as the tab label.

v18.8 update:
- Fixed remaining off-centre league-table rows.
- Added a `club-cell-inner` wrapper so the badge and club name align as one centred unit.
- Position badges, club crests, team names and numeric cells now share a consistent row height/centre line.
- Keeps explicit zone colours and all v18 Play-Off Mode features.

v18.9 update:
- Changed small table-header text such as "starts (subs)" to white.
- Fixes readability on the Stats page dark table header.
- Keeps v18.8 table-centering fixes and all Play-Off Mode features.

v18.10 update:
- Tightened and redesigned the Stats page.
- Added a narrower centred stats shell.
- Added summary cards for Apps, Goals, Assists and Cards.
- Reworked the player table with compact headers, initials avatars and tighter columns.
- Kept starts (subs) readable in white on the dark table header.

v18.11 update:
- Fixed Charlton Athletic and Birmingham City badge rendering on the Results/Around page.
- Results and Around now use `result_logo_for_team()`, which forces the corrected badge mapping for problem clubs.
- Added results-specific badge CSS so those crests preserve aspect ratio and render consistently.

v18.12 update:
- Completed match details on the Results page now include:
  - Role
  - Goals
  - Assists
  - Yellow cards
  - Red cards
  - Rating, if submitted
- Fixed the managed results query so YC/RC/rating are actually pulled into the details dropdown.
- Restyled the details panel with a better summary bar, player avatars, role chips and rating chips.

v18.13 update:
- Board confidence no longer displays/writes 100% while Derby are merely inside the target places with games still remaining.
- While the regular season is still active, inside target places is capped at 95%.
- 100% is reserved for when the target is actually secured at the end of the run.
- Updated the board message to say the job is not done yet.
- Fixed the confidence bar layout so 100% does not overlap or render awkwardly.

v18.14 update:
- Added a prominent Dashboard CTA when Derby qualify for the play-offs.
- If semi-final fixtures have not been created yet, the Dashboard now shows a "Generate Play-Offs" button.
- Once fixtures are generated, the Dashboard CTA changes to "Go to Play-Offs".
- Added a highlighted Play-Offs navigation tile when relevant.

v18.15 update:
- Added team logos to the Play-Offs page fixture list.
- Post Result button now only appears for Derby's next unplayed play-off match.
- Completed Derby play-off results can still be edited.
- Other semi-final tie is now simulated in the background so the user only has to play/post Derby matches.
- Board message now congratulates Derby on reaching the play-offs and wishes Jake well in the campaign.

v18.16 update:
- Play-off score posting now explicitly means score after extra time.
- Goals and assists are still captured normally against the after-extra-time score.
- Renamed the winner dropdown to "Penalty winner, if still level".
- Penalty winner is blank by default and only required if the final/tie remains level after extra time.
- Updated validation messages and Play-Offs page wording accordingly.

v18.16 final note:
- Kept the penalty winner dropdown default as "Not needed".
- Score wording still clearly says the posted score is after extra time.

v18.17 update:
- Penalty winner dropdown is now hidden for semi-final first legs.
- It only appears for:
  - Semi-final second leg
  - Final
- First-leg play-off posting now only asks for the score and normal player stats.

v18.18 update:
- Fixed board confidence after winning the play-offs.
- Play-off final victory / promotion achieved now records 100% board confidence.
- Losing the final or semi-final remains below 100%.
- This corrects the backwards behaviour where confidence could drop to 92% after promotion.

v18.19 update:
- Recalibrated board confidence:
  - Inside the target places before the season ends = max 85%
  - Play-offs reached / campaign underway = 85%
  - Promotion achieved = 100%
- Finishing in the top six no longer gives 100%.
- 100% is reserved for actually winning promotion.

v18.20 update:
- Recalibrated in-season board confidence:
  - Inside play-off places before the season ends = max 80%
  - Inside automatic promotion places before the season ends = max 90%
  - Play-offs secured / campaign underway = 85%
  - Promotion achieved = 100%
- This avoids treating a temporary top-six position as nearly complete, while still rewarding automatic-promotion form.

v18.21 update:
- Fixed the Stats / Squad contribution table row dividers so the border line is visually consistent across the full width.
- Removed the heavier-looking divider effect under the player-name column.
- Kept the rest of the Stats page styling intact.

v18.22 update:
- Changed the Completed Matches result label from "PES RESULT" to "RESULT".

v18.23 update:
- Made the Completed Matches details table more visual:
  - player initials
  - goals/assists chips
  - appearance role chips
  - yellow-card and red-card visual boxes
  - rating pill
  - notes column retained
- Added click-to-sort behaviour to the Stats page table headers.

v18.24 update:
- Refreshed the Career page Player Stats table with a more visual style:
  - player initial tiles
  - apps chip
  - goals and assists chips
  - rating pill
  - yellow and red card boxes
- Tidied the Challenge Timeline metric cards so "Games Left" stays on one line and the values are centred consistently.

v18.25 update:
- Restored the Dashboard hero-card proportions.
- Managed club card now vertically centres the Derby County badge/name within the card body.
- Next fixture card has more width and cleaner internal spacing so the opponent line and Post Result button no longer feel squashed.
- Board confidence card alignment has been kept consistent with the other two cards.

v18.26 update:
- Cleaned up the Stats page squad contribution table.
- Removed the heavier-looking border effect under the player-name column by switching to cell-level row dividers.
- Removed the extra-bold Apps styling so it matches the rest of the numeric columns more naturally.
- Removed the "starts (subs)" helper text from the page intro and the Apps header.

v18.27 update:
- Applied the Career-style coloured stat chips to the main Stats page table.
- Removed the "starts (subs)" sub-header from the Career page Player Stats table.
- Moved player-cell flex styling into inner wrapper elements so row borders render more consistently in both Stats and Career tables.

v18.28 update:
- Removed the duplicate competition title from the Table section header on the League Table page.
- The competition name now only appears once in the main page header.

v18.29 update:
- Enlarged the EFL Championship logo on the Home tab.
- Made the top Home dashboard tiles taller and less squashed.
- Improved spacing in Managed Club, Next Fixture and Board Confidence cards.
- Increased next-fixture logo/button breathing room.

v18.30 update:
- Hid the Complete tab from the main navigation until the challenge is actually ready to complete.
- Added a Dashboard call-to-action once the season/challenge reaches the decision point.
- The Complete link now appears only when:
  - the regular season is finished and no play-off run is pending, or
  - the play-off run has finished.

v18.31 update:
- Fixed the thicker divider under player names in the Career page Player Stats table.
- Restored the player-name column cell to normal table-cell behaviour.
- Kept the inner player/initials layout as flex so the visual styling remains.

v18.32 update:
- Forced the Home page EFL Championship logo to display much larger.
- Added a dedicated Home competition header class instead of relying on generic crest sizing.
- Set the Home competition crest to 76px desktop / 58px mobile.

v18.33 update:
- Fixed the Home internal server error from the newest patch.
- The /challenge-complete route decorator is now correctly attached to challenge_complete().
- Made the Complete navigation context processor defensive.
- Kept the larger Home EFL Championship logo and applied the Home header class to the actual Home hero.

v18.34 update:
- Fixed Home page proportions after the logo patch.
- Kept the EFL Championship logo large, but reduced the objective heading back to sensible size.
- Rebalanced the Managed Club, Next Fixture and Board Confidence tiles with equal columns and cleaner spacing.
- Hid the Challenge Complete navigation card until `complete_ready` is true.

v18.35 update:
- Added the same grey chip background behind the Apps values on the Stats tab table.
- Matches the visual treatment used on the Career page Player Stats table.

v18.36 update:
- Matches tab now only shows the Post button against the next unplayed fixture.
- Later fixtures show as Upcoming instead of allowing posting out of sequence.

v18.37 update:
- Removed the Backup Save tile from the Home / Challenge Centre dashboard.
- Backup remains available as a direct admin link at /admin/backup.

v18.38 update:
- Fixed Stats page Apps sorting.
- Apps sort now uses starts as the main value and subs as a tiny secondary value.
- Example: 2 starts sorts above 0 starts / 2 sub appearances.
- Added explicit data-sort values for other numeric stat columns too.

v18.39 update:
- Changed the Stats page AVG chip from yellow to grey.
- Keeps Yellow Cards visually yellow so AVG no longer clashes with the card column.

v18.40 update:
- Fixed play-off background simulation timing.
- Generate Play-Offs now creates the semi-final fixtures only.
- The non-human semi-final leg 1 is simulated only after Derby leg 1 is posted.
- The non-human semi-final leg 2 is simulated only after Derby leg 2 is posted.
- The final is generated only after both semi-finals are complete.

v18.41 update:
- Made Play-Off page action buttons compact and consistent with the status pills.
- Changed completed Derby play-off action from "Edit Derby result" to compact "Edit".
- Added scorer/assist chips underneath posted Derby play-off fixtures.
- App-simulated non-human ties still show as simulated because individual scorers are not tracked for those.

v18.42 update:
- Stats page now explicitly includes Derby play-off player events.
- The Stats aggregation now pulls from both regular managed fixtures and managed play-off fixtures.
- Play-off appearances, starts, sub apps, goals, assists, yellow cards, red cards and ratings feed through to the Stats tab.
- Added a Stats page note when play-off matches are included.

v18.43 update:
- Removed the Play-Off page edit action for completed Derby play-off results.
- Completed Derby play-off fixtures now show a passive Played status, matching the normal Results flow.

v18.44 update:
- Removed the unlocked jobs / available offers section from the Challenge Complete page.
- The underlying jobs logic remains untouched so it can be revisited later.

v18.45 update:
- Changed the Challenge Complete KPI from Games Posted to Record.
- Record now includes regular run-in matches plus managed Derby play-off matches.
- Manager record pills on Challenge Complete now use the combined regular + play-off record.
- Restored the Challenge Complete content while keeping jobs/offers hidden.
- Completion button no longer references job offers.

v18.46 update:
- Added direct admin correction page at /admin/edit-results.
- Admin page lists posted Derby regular results and Derby play-off results.
- Added admin edit forms for already-posted regular and play-off results.
- Corrections update score, human player stats, computer goals, cards, ratings and notes.
- Kept edit controls off the normal Matches / Play-Offs user flow.

v18.47 update:
- Restored the Home page Challenge Centre navigation tiles.
- Kept Backup Save hidden from Home.
- Kept Challenge Complete conditional so it only shows when complete_ready is true.

v18.48 update:
- Properly restored the Home page Challenge Centre tile grid using the original nav-card-grid markup.
- Removed Backup Save from the Home grid.
- Kept Challenge Complete conditional on complete_ready.
- Preserved the admin edit-results page and recent play-off/stat fixes.

v18.49 update:
- Added Render persistent-database support.
- If DATABASE_PATH is set, the app writes to that path.
- If /var/data exists, the app automatically writes to /var/data/pes_manager_career_v1.db.
- On a fresh persistent disk, the app seeds the live DB from the bundled starter database once.
- Added /admin/storage to show the active database path and whether the app is using persistent storage.
- Scores will persist across restarts/redeploys only after a Render persistent disk is attached, or DATABASE_PATH points to a persistent location.

v18.50 update:
- Added Supabase-backed SQLite save sync for Render Free.
- The app continues using the existing SQLite code locally, but DATABASE_URL now enables Supabase persistence.
- On startup, the app restores the SQLite save from Supabase if present.
- If Supabase is empty, the bundled starter DB is uploaded once as the initial save.
- After successful app requests, the live SQLite file is uploaded to Supabase.
- Added psycopg2-binary dependency for the Supabase Postgres connection.
- Updated /admin/storage to confirm Supabase save sync status.
- This avoids needing a paid Render persistent disk.

v18.51 update:
- Fixed the global Complete tab state check.
- The app now uses connect() instead of a missing get_db() helper.
- Complete tab readiness now checks the current/latest challenge, so it stays available after the challenge is marked Completed.
- Added direct admin diagnostic page at /admin/complete-debug.

v18.52 update:
- Fixed /challenge-complete 500 error caused by the route using regular-only manager_record while expecting play-off record fields.
- Challenge Complete page now uses combined_manager_record consistently.
- Removed the Complete link from the top navigation.
- Made the Challenge Complete tile available from the Home dashboard navigation grid.
- Added/kept /admin/complete-debug for diagnosis.
- Preserved Supabase save sync and admin edit results.

v18.53 update:
- Reworked final board verdict logic to account for objective outcome, manager record, points gained, table movement, margin to target, starting difficulty and relative squad strength.
- A missed objective is no longer automatically treated as a flat poor failure when the run-in performance is strong.
- Fixed verdict wording so it reads as the board speaking directly.
- Added a Performance Context panel to the Challenge Complete page.
- Challenge Complete board percentage now uses the realistic final assessment rather than the last regular-season board log only.

v18.54 update:
- Extended realistic board verdict logic into live progress views, not just the final Challenge Complete verdict.
- Dashboard and Manager pages now use contextual board confidence and assessment during the challenge.
- Post-result board logs now use contextual assessment, considering record, PPG, target gap, games remaining, table movement, squad strength and controllables.
- Challenge Complete progress verdict now uses the same context-aware language before the challenge is final.
- Added a Live Board View panel to Home and Manager pages.

v18.55 update:
- Removed Play-Offs from the top navigation bar.
- Play-Offs now appears from the Home/Dashboard only when the regular season is complete and Derby have qualified.
- Dashboard CTA uses Generate Play-Offs before fixtures exist, then Go to Play-Offs once fixtures are active.
- Added a conditional Play-Offs tile in the Home Challenge Centre grid only during an active play-off campaign.

v18.56 update:
- Removed Post from the top navigation bar.
- Post Result remains available from the Home/Dashboard action tile.
- Matches page next-fixture post access remains intact.
- Keeps the top navigation focused on main sections only.

v18.57 update:
- Added the same board-confidence progress bar treatment to the Board % KPI tile on the Challenge Complete page.
- Preserved the contextual final verdict and dashboard/manager board logic.

v18.58 update:
- Improved the completed-challenge transition state.
- After a challenge is marked Completed, the dashboard now shows Derby as an archived challenge and offers Next Job Offers / Career Timeline actions.
- The Post Result dashboard tile disappears after completion.
- Top navigation now shows Table/Matches/Results/Stats only while an active challenge exists.
- When there is no active challenge but at least one completed challenge, the top nav shows Jobs and Career instead.
- Derby archive data remains available through the dashboard and Career timeline; starting the next job creates a new active challenge without deleting Derby.

v18.59 update:
- Changed board verdict / assessment body copy to regular font weight for readability.
- Headings, labels, record chips and Board % remain bold.


v18.60 update:
- Fixed /challenge/<challenge_id> so Board Confidence uses the same contextual calculation as Home, Manager and Challenge Complete.
- This removes the stale 50% vs 78% mismatch on direct challenge URLs.
- Increased Challenge Complete performance-context text size for readability.
- Board verdict body copy remains regular weight.
- Win rate is now displayed as a whole number (for example 75% rather than 75.0%).


v18.61 update:
- Fixed the global navigation-state bug that could hide live challenge tabs near the completion point.
- Stats remains available until the challenge is explicitly marked Completed/locked.
- Replaced Challenge Complete Player Leaders with the same Player / Apps / G / A / Avg / Y / R table used on the Stats page.
- Challenge Complete player table is pre-sorted by average rating descending.


v18.62 update:
- League Table page now shows the latest completed round of results in a dedicated right-hand column, with club crests and scores.
- Matches Player Details dropdown now mirrors the Stats page visual treatment, including player initials, appearance, goals, assists, rating and cards.
- Increased Challenge Complete Board Assessment body text to 16px and Board Verdict body text to 20px for easier reading.


v18.63 update:
- Hidden the Jobs page from the visible UI for now.
- Removed Jobs from the top navigation after a completed challenge.
- Replaced completed-dashboard job-offer actions with Career Timeline / archive access.
- The /jobs route and underlying code remain in place for future development but are no longer surfaced to the user.


v18.64 update:
- Removed the duplicate Challenge Complete CTA from Home.
- Kept only the primary final-report action.
- Renamed the main button to 'View Final Report & Complete Challenge'.


v18.65 update:
- Renamed the main completion button to 'View Final Report'.
- Removed the Challenge Archived section from the Home page after completion.
- Completed challenges now keep the Home page cleaner and avoid implying another completion action.


v18.66 update:
- Added a safe one-off Middlesbrough 2020/21 next-challenge setup.
- New admin route: /admin/start-middlesbrough
- Preserves completed Derby and creates a new active challenge with clean stats/events.
- Seeds the actual Championship table after Matchday 38: Middlesbrough 9th, 56 points, six points from 6th.
- Seeds the actual Matchday 39-46 fixture schedule.
- Objective: Reach the Play-Offs (finish 6th or higher).
- Generalised Championship play-off copy so it uses the current managed club rather than hardcoded Derby text.


## v18.67
- Career Challenge Timeline now shows completed challenges using their final contextual board rating (Derby = 78%).
- Added Win Rate beside W-D-L on each Challenge Timeline card.
- Restored Manager to the top navigation while a challenge is active (`/manager`).
- New challenges begin at a neutral 50% board rating before any match is posted.
- Middlesbrough 2020/21 starts at 50% rather than inheriting a pre-match penalty from table context.


## v18.68

- Rebuilt CH002 Middlesbrough as Career Season 2 using only PES 2020-playable clubs.
- Career promotions: Leeds United, West Bromwich Albion and Brentford leave the Championship.
- Premier League relegations: AFC Bournemouth, Watford and Norwich City enter the Championship.
- The 2020/21 source scenario is continuity-mapped: Brentford→Fulham, Coventry→Charlton, Rotherham→Wigan, Wycombe→Hull.
- Middlesbrough remain 9th on 56 points, six points behind 6th-place Bournemouth on 62, with eight matches remaining.
- CH001 Derby history is preserved; CH002 starts unplayed with neutral 50% board confidence.


## v18.69

- Corrected PES 2020 simulation ratings for AFC Bournemouth, Watford and Norwich City in Career Season 2.
- AFC Bournemouth: 77 overall, 77 defence, 78 midfield, 78 attack.
- Watford: 78 overall, 76 defence, 79 midfield, 78 attack.
- Norwich City: 74 overall, 74 defence, 74 midfield, 77 attack.
- Rating sources are stored in `team_rating_sources` and the `teams` simulation values are updated accordingly.


## v18.70
- Fixed live/Supabase CH002 migration: an unplayed Middlesbrough save using the old 2020/21 club list is automatically rebuilt to the Career Season 2 PES 2020-compatible league.
- Career Season 2 clubs: 2019/20 Championship pool minus Leeds United, West Bromwich Albion and Brentford, plus AFC Bournemouth, Watford and Norwich City.
- Middlesbrough remain 9th on 56 points, six points behind 6th-place AFC Bournemouth on 62.
- Derby CH001 history is preserved and CH002 is never rewritten once a CH002 fixture has been played.


## Read-only challenge archive

`/admin/challenge-archive` lists saved challenges, their tables, objectives, latest recorded board assessments, league results and play-off results. Filter with `?challenge_id=CH001`. Download the same records from `/admin/challenge-archive/export.json` or `/admin/challenge-archive/export.csv`; both accept the same filter.

The archive and its JSON/CSV exports are public and read-only. No login or Render password setting is required. Anyone with the URL can view and download the challenge records. All archive responses disable caching.

The archive opens the application's selected SQLite working save with `mode=ro` and `query_only=ON`, within a consistent read transaction. It does not call writable `connect()`, run schema/season repairs, generate matches, or upload the save to Supabase. A missing database or required schema returns 503; the archive does not substitute another database. In Supabase mode this reads the local working save that the application restores/syncs, not a separate direct query to Postgres. It does not prove that an earlier application startup successfully restored the latest remote save.

Tables are labelled final only for Completed challenges with recorded scores for all stored fixtures and every table team having played `final_round` games. Automatic promotion and relegation are calculated only for a complete 24-team EFL Championship table with unique positions. Play-off promotion additionally needs a recorded played final, complete scores, and a valid winner (including a stored penalty winner for a draw). Other competitions, missing finals, incomplete seasons and unresolved ties remain unconfirmed. Original objectives and recorded board assessments are shown without replacing them with generated verdicts. CSV protects text cells against spreadsheet formula execution.

Validation: `python -m unittest discover -s tests -v` (requires Flask). Tests use synthetic records plus a temporary copy of the bundled SQLite file, not the live save. No database or credentials are changed by this feature.

