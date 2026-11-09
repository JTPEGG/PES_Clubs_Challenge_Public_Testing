"""Presentation-only FM-inspired desktop dashboard for the transfer window.

The functions below rearrange existing server-rendered cards into client-side
panels. They never submit transfer decisions or bypass existing server checks.
Without JavaScript, the original transfer page stays readable and usable.
"""

DASHBOARD_CSS = r"""
:root{--desk-bg:#0b1421;--desk-panel:#152439;--desk-panel2:#1b2e45;--desk-stroke:#304b64;--desk-accent:#52b6df;--desk-green:#6eddb4;--desk-faint:#a6bfd3}
body.desk-ui{background:var(--desk-bg);color:#f2f7fc;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}
body.desk-ui *{scroll-margin-top:100px}
body.desk-ui [hidden]{display:none!important}
.desk-topbar{position:sticky;top:0;z-index:30;display:flex;align-items:center;justify-content:space-between;gap:15px;padding:11px clamp(14px,3vw,38px);background:#112136;border-bottom:1px solid #38506b;box-shadow:0 3px 20px #02091370}
.desk-brand{display:flex;align-items:center;gap:12px;min-width:0;color:#f5faff;text-decoration:none}
.desk-logo{width:40px;height:40px;display:grid;place-items:center;font-weight:900;letter-spacing:-.08em;font-size:15px;background:linear-gradient(145deg,#45bcd5,#26698c);color:#081725;border-radius:9px;box-shadow:inset 0 1px 0 #ffffff55}
.desk-brand strong{display:block;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.desk-brand small{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#a9c9d9}
.desk-header-right{display:flex;align-items:center;gap:20px}
.desk-header-tag{color:#a9c8de;font-size:12px}
.desk-header-tag strong{color:white}
.desk-live-status{display:inline-flex;align-items:center;gap:7px;color:#a4e6ca;font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
.desk-live-status:before{content:"";width:7px;height:7px;border-radius:100%;background:#6eddb4;box-shadow:0 0 0 4px #6eddb420}
.desk-live-status.closed{color:#b6c2d2}
.desk-live-status.closed:before{background:#8ca1b2;box-shadow:none}
.desk-header-clock{border-left:1px solid #49647c;padding-left:18px;min-width:91px;white-space:nowrap}
.desk-header-clock small{display:block;color:#a5bdce;font-size:10px;text-transform:uppercase;letter-spacing:.1em}
.desk-header-clock strong{font-variant-numeric:tabular-nums;font-size:23px;font-weight:850;line-height:1.1;color:#f8fcff}
.desk-shell{max-width:1570px;margin:0 auto!important;display:grid;grid-template-columns:216px minmax(0,1fr);gap:0;padding:0!important;min-height:calc(100vh - 63px)}
/* A spectator has no manager sidebar: occupy the FULL grid, not its 216px first column. */
body.desk-ui[data-spectator="true"] .desk-shell{grid-template-columns:minmax(0,1fr)}
body.desk-ui[data-spectator="true"] .desk-workspace{width:100%;max-width:1440px;margin:0 auto}

.desk-sidebar{padding:24px 13px 22px;border-right:1px solid #2a4057;background:#101e2e;min-width:0}
.desk-nav-label{padding:5px 14px 13px;color:#839bb0;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.14em}
.desk-tab{width:100%;display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:left;border:1px solid transparent;background:transparent;color:#b9cad9;padding:11px 13px;border-radius:8px;margin:2px 0;font-size:14px;font-weight:650;cursor:pointer;text-decoration:none}
.desk-tab:hover{background:#25374d;color:white}
.desk-tab[aria-current="page"]{border-color:#3d6d86;background:#1e4159;color:#ebfaff;box-shadow:inset 3px 0 var(--desk-accent)}
.desk-tab .desk-nav-icon{font-size:16px;display:inline-block;width:21px;text-align:center}
.desk-tab .desk-nav-text{flex:1}
.desk-nav-count{min-width:23px;text-align:center;padding:2px 6px;border-radius:18px;background:#31556c;font-size:11px;color:#e1f5ff;font-variant-numeric:tabular-nums}
.desk-sidebar-foot{padding:14px;margin-top:30px;border-top:1px solid #2c4155;color:#8ba3b7;font-size:12px}
.desk-sidebar-foot a{color:#abcce0}
.desk-workspace{padding:26px clamp(16px,3vw,44px) 70px;min-width:0}
.desk-intro{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px;border-bottom:1px solid #284056;padding-bottom:15px}
.desk-intro h1{font-size:26px;letter-spacing:-.025em;margin:2px 0 3px}
.desk-intro .muted{font-size:13px;margin:1px 0}
.desk-section-kicker{font-size:11px;color:#86a9bf;text-transform:uppercase;letter-spacing:.12em;font-weight:750;margin:0}
.desk-mobile-tabs{display:none}
.desk-view h2{font-size:21px;letter-spacing:-.025em;margin:22px 0 12px}
.desk-view h3{font-size:16px}
.desk-view .card{background:var(--desk-panel);border:1px solid var(--desk-stroke);border-radius:11px;box-shadow:0 4px 18px #030c161c}
.desk-view .grid{grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:12px}
.desk-view .offer{border-left:3px solid var(--desk-accent);background:#192d43;transition:border-color .16s,background .16s}
.desk-view .offer:focus-within{border-color:#67c9ed;background:#203a53}
.desk-view .offer .label{color:#afd2e4}
.desk-view .offer h3{font-size:17px;margin-top:8px}
.desk-view .muted,.desk-view .time-note{color:#bacadb}
.desk-view .count{color:var(--desk-green)}
.desk-view button:not(.desk-tab):not(.desk-filter-button):hover{filter:brightness(1.14)}
.desk-view button:focus-visible,.desk-tab:focus-visible,.desk-filter-button:focus-visible{outline:2px solid #80cdec;outline-offset:2px}
.desk-view .card form{max-width:100%}
.desk-view .card label{color:#bcd4e3}
.desk-view input,.desk-view select{max-width:100%}
.desk-view .scout-filters{background:#122337;border-radius:8px;padding:13px;margin:14px 0}
.desk-view .scout-table{border:1px solid #36516b;border-radius:8px}
.desk-view .scout-table th{background:#203954}
.desk-scout-pager{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:15px 0 6px;color:#c9e0ed;font-size:13px}
.desk-scout-pager-actions{display:flex;align-items:center;gap:8px}
.desk-page-link{display:inline-flex;align-items:center;justify-content:center;min-width:90px;padding:9px 12px;border:1px solid #4d839e;background:#214962;border-radius:8px;color:#e7f7ff;text-decoration:none;font-weight:700}
.desk-page-link:hover,.desk-page-link:focus-visible{background:#2d6683;color:#fff}
.desk-view[data-view="scouting"] .desk-scout-pager{position:relative;z-index:1}
.desk-scout-finance{display:flex;flex-wrap:wrap;gap:9px;margin:0 0 12px}
.desk-scout-finance span{border:1px solid #426982;background:#213b54;border-radius:8px;padding:10px 14px;color:#c5e1f2}
.desk-scout-finance b{display:block;color:#fff;font-size:18px;margin-top:3px}
.desk-view[data-view="scouting"] .scout-table{max-height:none;overflow-y:visible}
.desk-view[data-view="scouting"] [data-scout-results] td{white-space:nowrap}
.desk-view[data-view="scouting"] table[data-scout-results]:not(.desk-show-attributes) .desk-scout-extra{display:none!important}
.desk-scout-table-tools{display:flex;justify-content:flex-end;margin:10px 0 8px}
.desk-scout-table-tools button{font-size:12px;padding:6px 11px}
.desk-view[data-view="scouting"] [data-scout-progress]{padding:12px 0 20px}
.desk-view .scout-table tbody tr:hover{background:#28415a}
.desk-view .scout-table a{color:#bce6ff}
.desk-view .pill{background:#294660}
.desk-view .budget-track{height:10px;background:#30445c}
.desk-empty{margin:20px 0;background:#16283a;border:1px dashed #47647a;border-radius:12px;padding:26px;color:#b5cadb}
.desk-empty strong{color:#f6faff}
.desk-actions-bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0 17px}
.desk-action-tile{padding:17px;text-align:left;border:1px solid #3e6077;border-radius:10px;background:#192f45;color:#eef7fb;flex:1 1 190px;cursor:pointer;font:inherit}
.desk-action-tile:hover{background:#244b60;transform:translateY(-1px)}
.desk-action-tile strong{display:block;font-size:15px}
.desk-action-tile small{display:block;font-size:12px;color:#b2ccdb}
.desk-view-title{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.desk-view-title .pill{font-size:12px}
.desk-view-header{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.desk-view-header h2{margin:9px 0 0}
.desk-view-header .muted{margin:3px 0}
.desk-inbox-tools{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:10px 0 12px}
.desk-inbox-list{display:block!important;border:1px solid #36516a;border-radius:8px;overflow:hidden;background:#14263b}
.desk-inbox-columns,.desk-inbox-item>summary{display:grid;grid-template-columns:34px minmax(150px,1.5fr) minmax(120px,1.1fr) 105px minmax(115px,.9fr);align-items:center;gap:11px}
.desk-inbox-columns{padding:9px 13px;background:#223a52;font-size:11px;font-weight:750;color:#b8d0e2;text-transform:uppercase;letter-spacing:.04em}
.desk-inbox-item{border-bottom:1px solid #30475e}
.desk-inbox-item:last-child{border-bottom:0}
.desk-inbox-item>summary{min-height:47px;cursor:pointer;padding:8px 13px;font-size:13px;list-style:none}
.desk-inbox-item>summary::-webkit-details-marker{display:none}
.desk-inbox-item>summary:hover{background:#234059}
.desk-inbox-item[open]>summary{background:#244157}
.desk-inbox-item[data-action-needed="true"]>summary{background:#19344a}
.desk-inbox-flag{display:inline-grid;place-items:center;width:18px;height:18px;border:1px solid #5b7891;border-radius:4px;color:transparent;font-weight:900}
.desk-inbox-item[data-action-needed="true"] .desk-inbox-flag{color:#13283b;background:#ffcf70;border-color:#ffcf70}
.desk-inbox-subject{font-weight:700;color:#eaf5ff;overflow:hidden;text-overflow:ellipsis}
.desk-inbox-sender{color:#c2dbeb;overflow:hidden;text-overflow:ellipsis}
.desk-inbox-fee{font-variant-numeric:tabular-nums;color:#8be3c6;font-weight:700;text-align:right}
.desk-inbox-state{color:#c9ddeb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.desk-inbox-item[data-status="agreed_future"] .desk-inbox-state,.desk-inbox-item[data-status="completed"] .desk-inbox-state{color:#86e0b8}
.desk-inbox-item .desk-inbox-detail{padding:12px 16px 15px 49px;background:#0f1d2e}
.desk-inbox-item .desk-inbox-detail>.offer{margin:0!important;border:1px solid #365570;border-radius:6px;padding:12px!important;background:#172b41}
.desk-inbox-item .desk-inbox-detail>.offer .actions{display:flex;gap:8px;flex-wrap:wrap}
.desk-transfer-cancel-form{margin:0!important;display:inline-flex!important}
.desk-transfer-cancel{padding:1px 6px!important;width:26px;height:26px;line-height:1;font-size:20px!important;font-weight:650!important;border:1px solid #a86774!important;color:#ffcbd3!important;background:#5a2d38!important;border-radius:5px!important}
.desk-transfer-cancel:hover{background:#803e4d!important}
@media(max-width:720px){.desk-inbox-columns,.desk-inbox-item>summary{grid-template-columns:24px minmax(100px,1.5fr) minmax(92px,1fr) minmax(80px,.7fr);gap:7px}.desk-inbox-columns span:nth-child(5),.desk-inbox-state{display:none}.desk-inbox-item>summary{padding:9px}.desk-inbox-item .desk-inbox-detail{padding:9px}}

.desk-live-offer-stream:not([hidden]){display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin:14px 0 18px}
.desk-live-offer-stream .offer{margin:0;border-color:#4384a4}
.desk-live-offer-stream .actions{display:flex;flex-wrap:wrap;gap:8px}
.desk-decision-feedback{margin:9px 0 2px;font-size:13px;font-weight:650;color:#b9e5ed}
.desk-decision-feedback[data-error="1"]{color:#ffb5a5}
.desk-inline-agent-note{margin:9px 0 3px;color:#bad7e5;font-size:12px}
.desk-ui .offer form button:disabled{opacity:.62;cursor:wait}
.desk-offer-toast{position:fixed;bottom:24px;right:24px;max-width:min(420px,calc(100vw - 30px));z-index:90;border:1px solid #62b6d6;border-radius:10px;padding:15px 18px;background:#173d56;box-shadow:0 12px 35px #000a;color:white;font-weight:750;text-align:left;cursor:pointer}
.desk-inbox-tools input{flex:1 1 225px;max-width:320px;font-size:13px;padding:9px 11px}
.desk-filter-button{padding:8px 12px!important;font-size:12px!important;border-radius:7px;background:#1b3148;color:#b6cbdc;border:1px solid #426076;cursor:pointer;font-weight:650}
.desk-filter-button:hover{background:#2b5068;color:#fff}
.desk-filter-button[aria-pressed="true"]{background:#1c5972;border-color:#67bcdc;color:#fff}
.desk-player-quickfilter{padding:2px 0!important;border:0!important;background:transparent!important;color:#e8faff!important;text-align:left;font-size:17px!important;font-weight:750!important;text-decoration:none;cursor:pointer}
.desk-player-quickfilter:hover{text-decoration:underline}
.desk-grouped-offer{grid-column:1/-1;border:1px solid #47647e;border-radius:12px;background:#112237;overflow:hidden;margin:3px 0 6px}
.desk-grouped-offer>summary{cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:12px;background:#214159;padding:13px 16px;font-size:15px;font-weight:800}
.desk-grouped-offer>summary::-webkit-details-marker{display:none}
.desk-grouped-offer>summary::after{content:"▾";font-size:15px;color:#8ecde9}
.desk-grouped-offer:not([open])>summary::after{content:"▸"}
.desk-grouped-offer .desk-grouped-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px;padding:10px}
.desk-grouped-offer .desk-grouped-grid .card{margin:0}
.desk-group-count{font-size:12px;color:#c3e3f2;font-weight:600}
.desk-finance-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.desk-finance-grid .card{margin:0}
.desk-finance-value{font-size:27px;font-weight:850;margin:6px 0;color:#f5faff;letter-spacing:-.025em;font-variant-numeric:tabular-nums}
.desk-finance-track{height:10px;border-radius:20px;background:#314760;overflow:hidden;margin:12px 0}
.desk-finance-fill{height:100%;border-radius:20px;background:#6eddb4}
.desk-player-profile{color:#eefaff!important;text-decoration:none;font-weight:800}
.desk-player-profile:hover{text-decoration:underline;color:#74d7f6!important}
.desk-rebid-form{display:flex;flex-wrap:wrap;gap:8px;align-items:end}
.desk-rebid-form label{display:flex;flex-direction:column;gap:5px;font-size:12px}
.desk-rebid-form input{width:170px}
.agent-opening-quote{padding:10px 12px;border-radius:7px;
  border:1px solid #327d7d;background:#153e49;color:#bbede8}
.desk-post-window-next{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.desk-post-window-next a{font-weight:750;color:#8de1ff}
.desk-setup-card{max-width:920px}
.desk-setup-step{margin:5px 0}
.desk-setup-step button{width:100%;display:flex;align-items:center;gap:14px;
  border:1px solid #365773;border-radius:8px;background:#172d43;
  text-align:left;padding:12px 14px;color:#eaf8ff;font:inherit;cursor:pointer}
.desk-setup-step button:hover{background:#234861}
.desk-setup-check{font-size:23px;line-height:1;color:#67d9b4}
.desk-setup-done{color:#89eac5}
.desk-transfer-split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;align-items:start}
.desk-transfer-section{min-width:0;margin:0!important}
.desk-transfer-section>h3{display:flex;align-items:center;gap:9px;margin:0 0 14px;font-size:18px!important}
.desk-direction{width:27px;height:27px;border-radius:6px;display:grid;place-items:center;font-size:21px;font-weight:900}
.desk-direction.in{color:#9cf6c5;background:#155642}
.desk-direction.out{color:#ffc6b0;background:#6a3c30}
.desk-section-count{background:#29455f;color:#bce7f8;font-size:12px;padding:3px 8px;border-radius:30px}
.desk-squad-table table{min-width:650px}
.desk-squad-table th,.desk-squad-table td{padding:5px 8px!important;line-height:1.2;vertical-align:middle}
.desk-squad-table select{padding:5px!important;font-size:12px;max-width:145px}
.desk-squad-table button{padding:5px 8px!important;font-size:11px!important}
.desk-squad-table label{font-size:11px!important}
.desk-squad-table input[type=checkbox]{width:15px;height:15px;padding:0}
.desk-squad-table form{gap:5px;align-items:center}
.desk-table-sort{font-size:inherit!important;font-weight:800!important;line-height:inherit!important;padding:0!important;
 background:transparent!important;border:0!important;color:inherit!important;text-align:left;cursor:pointer}
.desk-table-sort::after{content:' ↕';font-size:11px;color:#80abc1}
.desk-table-sort[aria-sort="ascending"]::after{content:' ↑';color:#7cdbff}
.desk-table-sort[aria-sort="descending"]::after{content:' ↓';color:#7cdbff}
.desk-table-filter-row input{font-size:11px;width:100%;min-width:45px;padding:5px!important;background:#15293d}
.desk-table-filter-row th{padding:5px!important}
.desk-cell-quickfilter{cursor:pointer}
.desk-cell-quickfilter:hover{background:#335a70}
.desk-ui .desk-view .scout-table{max-width:100%;overflow-x:auto}
.desk-transfer-section .scout-table{max-height:530px}
.desk-transfer-section table{width:100%;font-size:12px;min-width:300px}
.desk-transfer-section table td,.desk-transfer-section table th{white-space:normal;overflow-wrap:break-word}
.desk-transfer-section table td:nth-child(3){white-space:nowrap}
.desk-view .desk-market-table table{min-width:590px}
@media(max-width:1080px){.desk-transfer-split{grid-template-columns:1fr}}
@media(max-width:650px){.desk-transfer-section{padding:12px!important}.desk-transfer-section table{font-size:11px}
 .desk-squad-table th,.desk-squad-table td{padding:4px 6px!important}}
.desk-provenance{font-size:11px;color:#7895a8;margin-top:26px}
.desk-global-message{margin:12px 0;border-radius:9px;border:1px solid #426b84;background:#153a4c;padding:11px 16px}
.desk-global-message.alert{border-color:#a87254;background:#4a332d}
body.desk-ui main .clock{font-size:clamp(36px,4vw,53px)}
.desk-view .feed .card{border-left:2px solid #517b99}
.desk-view .grid>.card{margin:0}
@media(max-width:940px){
 .desk-shell{grid-template-columns:70px minmax(0,1fr)}
 .desk-sidebar{padding:20px 7px}
 .desk-nav-label,.desk-nav-text,.desk-nav-count,.desk-sidebar-foot{display:none}
 .desk-tab{justify-content:center;padding:12px 6px}
 .desk-tab .desk-nav-icon{width:auto}
 .desk-header-tag{display:none}
}
@media(max-width:650px){
 .desk-topbar{padding:10px 13px;gap:9px}
 .desk-brand strong{font-size:12px;max-width:150px}
 .desk-brand small{font-size:9px}
 .desk-logo{width:34px;height:34px;font-size:13px}
 .desk-header-right{gap:8px}
 .desk-live-status{display:none}
 .desk-header-clock{padding-left:9px;min-width:69px}
 .desk-header-clock strong{font-size:18px}
 .desk-shell{display:block;min-height:calc(100vh - 60px)}
 .desk-sidebar{display:none}
 .desk-workspace{padding:15px 13px 55px}
 .desk-mobile-tabs{display:flex;gap:6px;overflow-x:auto;scrollbar-width:thin;border-bottom:1px solid #324a60;padding:0 0 11px;margin:4px -1px 13px}
 .desk-mobile-tabs .desk-tab{width:auto;flex:none;white-space:nowrap;font-size:12px;padding:9px 12px}
 .desk-mobile-tabs .desk-tab .desk-nav-icon{font-size:13px}
 .desk-intro h1{font-size:21px}
 .desk-view h2{font-size:19px}
 .desk-grouped-offer .desk-grouped-grid{grid-template-columns:minmax(0,1fr)}
 .desk-view .grid{grid-template-columns:minmax(0,1fr)}
 .desk-view input[type=number]{width:132px}
}

/* Squad controls: one calm, fixed-height row; player instructions separate. */
.desk-squad-switch{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:10px 0 15px}
.desk-squad-switch button{padding:9px 17px;background:#182a3d;border:1px solid #36536e;border-radius:7px;color:#bad3e5;font-size:13px;font-weight:730;cursor:pointer}
.desk-squad-switch button[aria-pressed="true"]{background:#205878;border-color:#69c5e5;color:white}
.desk-squad-count{margin-left:auto;font-size:12px;color:#97b4c8}
.desk-view .desk-compact-squad{padding:11px 13px;margin:0}
.desk-compact-squad .scout-table{max-height:none!important;overflow:auto}
.desk-compact-squad table{margin:0!important;min-width:860px!important;table-layout:auto;border-collapse:collapse}
.desk-compact-squad thead th{position:sticky;top:0;z-index:2;text-align:left}
.desk-compact-squad td,.desk-compact-squad th{padding:5px 8px!important;line-height:1.18!important;white-space:nowrap!important;vertical-align:middle!important;height:37px}
.desk-compact-squad .desk-table-filter-row th{height:31px}
.desk-compact-squad .desk-squad-name{min-width:180px;max-width:300px;font-weight:680}
.desk-compact-squad .desk-squad-name a{text-decoration:none;color:#eef8ff}
.desk-compact-squad .desk-squad-name a:hover{text-decoration:underline}
.desk-compact-squad .desk-squad-arrival,.desk-compact-squad .desk-squad-request{font-size:10px;margin-left:6px;border:1px solid #397d86;border-radius:5px;padding:2px 5px;color:#b5e8d9;font-weight:700}
.desk-compact-squad .desk-squad-request{border-color:#9b714a;color:#f8cf9b}
.desk-compact-squad td select{width:136px!important;max-width:136px!important;height:27px;padding:3px 6px!important;font-size:11px!important;border-radius:5px}
.desk-compact-squad .desk-squad-listed label{display:inline-flex!important;align-items:center;gap:7px;margin:0!important;white-space:nowrap}
.desk-compact-squad .desk-squad-listed input{width:15px;height:15px;accent-color:#68cbdf;padding:0}
.desk-compact-squad .desk-squad-actions form{display:flex;align-items:center;gap:5px;flex-wrap:nowrap;margin:0;padding:0}
.desk-compact-squad .desk-squad-actions button{font-size:11px!important;padding:5px 9px!important;line-height:1.2!important;white-space:nowrap;border-radius:5px}
.desk-compact-squad .desk-squad-offer{background:#183b52;border-color:#437a94}
.desk-squad-extras{margin:8px 4px 0;color:#b3cade;font-size:13px}
.desk-squad-extras summary{cursor:pointer;padding:8px 0}
.desk-squad-notice{padding:7px 12px;margin:4px 0;color:#b9eccc;font-size:12px}
.desk-tactics-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;background:#15283c;border:1px solid #334c65;border-radius:10px;padding:13px 15px;margin-bottom:14px}
.desk-tactics-toolbar label{display:flex;align-items:center;gap:9px;margin:0;color:#cbdbe8;font-size:13px;font-weight:720}
.desk-tactics-toolbar select{padding:7px 10px;font-size:13px}
.desk-tactics-toolbar .muted{font-size:11px;flex:1 1 200px}
.desk-tactics-toolbar button{padding:8px 13px;border-radius:7px;font-size:12px;font-weight:750}
.desk-tactics-toolbar [data-tactics-save]{background:#2780a8;border-color:#4bb7d7}
.desk-tactics-save-status{min-width:80px;color:#a9ddce;font-size:12px}
.desk-tactics-layout{display:grid;grid-template-columns:minmax(390px,1.5fr) minmax(245px,1fr);gap:16px;align-items:start}
.desk-pitch-wrap{border:1px solid #375266;border-radius:12px;padding:12px;background:#13243a;min-width:0}
.desk-pitch{position:relative;aspect-ratio:1.2 / 1;max-height:650px;border-radius:6px;overflow:hidden;background:repeating-linear-gradient(to bottom,#194d40 0%,#194d40 12.5%,#215845 12.5%,#215845 25%);border:2px solid #60977c;touch-action:pan-y}
.desk-pitch-boundary{position:absolute;inset:5%;border:1.5px solid #b5d5b7a6;pointer-events:none}
.desk-pitch-midline{position:absolute;left:5%;right:5%;top:50%;border-top:1.5px solid #b5d5b7a6;pointer-events:none}
.desk-pitch-circle{position:absolute;left:41%;top:39%;width:18%;aspect-ratio:1;border:1.5px solid #b5d5b7a6;border-radius:100%;pointer-events:none}
.desk-pitch-box{position:absolute;left:25%;width:50%;height:17%;border:1.5px solid #b5d5b7a6;pointer-events:none}
.desk-pitch-box-top{top:5%}.desk-pitch-box-bottom{bottom:5%}
.desk-pitch-goal{position:absolute;left:40%;width:20%;height:4%;border:1.5px solid #b5d5b7a6;pointer-events:none}
.desk-pitch-goal-top{top:1%}.desk-pitch-goal-bottom{bottom:1%}
.desk-pitch-spot{position:absolute;left:49.5%;width:1%;aspect-ratio:1;border-radius:50%;background:#b5d5b7;pointer-events:none}
.desk-pitch-spot-top{top:15%}.desk-pitch-spot-bottom{bottom:15%}
.desk-pitch [data-pitch-players]{position:absolute;inset:0;pointer-events:none}
.desk-pitch-token{position:absolute;transform:translate(-50%,-50%);width:110px;max-width:21%;display:flex;flex-direction:column;align-items:center;gap:3px;background:transparent!important;border:0!important;padding:2px!important;color:white;cursor:grab;pointer-events:auto;touch-action:none;z-index:4}
.desk-pitch-token:active{cursor:grabbing}
.desk-pitch-token .desk-player-disc{display:grid;place-items:center;width:31px;height:31px;flex:none;border-radius:50%;background:#112878;border:2px solid #eac746;box-shadow:0 2px 9px #06131f9c;color:#fff5b0;font-size:12px;font-weight:850}
.desk-pitch-token .desk-player-name{max-width:100%;font-size:10px;line-height:1.2;font-weight:750;text-shadow:0 2px 4px #07190e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:white}
.desk-pitch-token .desk-player-position{font-size:9px;color:#e5f3dd}
.desk-pitch-token[data-selected="true"] .desk-player-disc{border-color:white;box-shadow:0 0 0 4px #8ce9cf88}
.desk-pitch-caption{margin:10px 2px 0;text-align:center;font-size:12px;color:#b6cfdf;font-weight:750}
.desk-tactics-roster{display:grid;gap:12px;min-width:0}
.desk-tactics-group{background:#15293e;border:1px solid #37536d;border-radius:10px;min-width:0;overflow:hidden}
.desk-tactics-group>header{position:static;display:flex;justify-content:space-between;align-items:center;gap:10px;background:#203a53;padding:12px 13px;font-size:13px;border-bottom:1px solid #3c5b70}
.desk-tactics-group header span{color:#98c7d4;font-size:12px}
.desk-tactics-player-list{padding:9px;min-height:70px;display:grid;gap:5px}
.desk-tactics-player{display:flex;gap:8px;align-items:center;background:#1c354b;border:1px solid #35536c;border-radius:7px;padding:6px 7px;min-width:0;cursor:grab}
.desk-tactics-player[data-selected="true"]{border-color:#94e2d2;background:#264c5e}
.desk-tactics-player strong{font-size:12px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.desk-tactics-player .desk-tactics-pos{font-size:10px;color:#aacfe2;min-width:30px}
.desk-tactics-player .desk-tactics-ovr{font-size:12px;color:#a9e8c4;font-variant-numeric:tabular-nums}
.desk-tactics-player select{max-width:87px;font-size:10px;padding:4px 3px;border-radius:4px}
.desk-tactics-group .desk-drop-action{display:block;margin:0 9px 9px;padding:6px 9px;background:#1b4559;border:1px dashed #5b8aa3;font-size:11px;color:#d3eaf3}
.desk-tactics-hint{font-size:12px;color:#9eb6c6;line-height:1.5;margin:12px 0 0}
@media(max-width:930px){.desk-tactics-layout{grid-template-columns:minmax(0,1fr)}.desk-pitch-wrap{max-width:680px;margin:0 auto;width:100%}.desk-tactics-roster{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:600px){.desk-tactics-roster{grid-template-columns:1fr}.desk-tactics-toolbar{gap:8px}.desk-pitch-token{width:81px}.desk-pitch-token .desk-player-name{font-size:9px}.desk-pitch-token .desk-player-disc{width:27px;height:27px;font-size:11px}}

/* FM-like message list and adjacent reading pane */
.desk-inbox-split{display:grid;grid-template-columns:minmax(245px,315px) minmax(0,1fr);border:1px solid #36516a;background:#102035;border-radius:10px;overflow:hidden;min-height:520px}
.desk-inbox-split .desk-inbox-list{border:0;border-right:1px solid #35506a;border-radius:0;min-width:0;max-height:75vh;overflow-y:auto}
.desk-inbox-split .desk-inbox-columns,.desk-inbox-split .desk-inbox-item>summary{display:grid;grid-template-columns:22px minmax(0,1fr) 74px;column-gap:8px;row-gap:3px}
.desk-inbox-split .desk-inbox-columns{grid-template-columns:22px 1fr;padding:11px}
.desk-inbox-split .desk-inbox-columns span:nth-child(n+3){display:none}
.desk-inbox-split .desk-inbox-item>summary{padding:13px 10px;min-height:64px}
.desk-inbox-split .desk-inbox-flag{grid-row:1/3;align-self:center}
.desk-inbox-split .desk-inbox-subject{grid-column:2;grid-row:1}
.desk-inbox-split .desk-inbox-sender{grid-column:2;grid-row:2;font-size:11px;color:#91afc3}
.desk-inbox-split .desk-inbox-fee{grid-column:3;grid-row:1;font-size:12px}
.desk-inbox-split .desk-inbox-state{grid-column:3;grid-row:2;font-size:10px;display:block!important;text-align:right}
.desk-inbox-split .desk-inbox-item[data-selected="true"]>summary{background:#24506a;box-shadow:inset 3px 0 #70c7e8}
.desk-inbox-reader{padding:0;min-width:0}
.desk-inbox-reader-header{padding:17px 21px;background:#1a3149;border-bottom:1px solid #38516c;display:flex;justify-content:space-between;gap:12px;align-items:center}
.desk-inbox-reader-header strong{font-size:16px}
.desk-inbox-reader-header small{display:block;margin-top:4px;font-size:12px;color:#a9c5d6}
.desk-inbox-reader .desk-inbox-detail{padding:19px 21px}
.desk-inbox-reader .desk-inbox-detail .offer{background:transparent!important;border:none!important;padding:0!important}
.desk-inbox-reader .desk-inbox-detail .count{font-size:22px}
.desk-inbox-reader-empty{padding:42px 24px;color:#9ebbcf;text-align:center}
@media(max-width:760px){.desk-inbox-split{grid-template-columns:1fr}.desk-inbox-split .desk-inbox-list{border-right:0;border-bottom:1px solid #35506a;max-height:275px}.desk-inbox-reader{min-height:220px}.desk-inbox-reader .desk-inbox-detail{padding:13px}}
/* Minimal scouting search and modal condition builder */
.desk-scout-searchbar{display:flex;align-items:end;gap:9px;flex-wrap:wrap;background:#162b40;border:1px solid #385773;border-radius:9px;padding:12px 14px}
.desk-scout-searchbar>label:first-child{flex:1 1 215px;max-width:430px}
.desk-scout-searchbar input[type="search"],.desk-scout-searchbar input[name="scout_query"]{width:100%;padding:9px}
.desk-scout-searchbar>label{font-size:12px;min-width:130px}
.desk-scout-searchbar select{font-size:12px}
.desk-scout-add,.desk-scout-clear{padding:9px 13px!important;border-radius:6px!important;font-size:12px!important;font-weight:720!important}
.desk-scout-add{background:#25769c!important;color:white!important;border:1px solid #63b6d8!important}
.desk-scout-clear{background:#23384d!important;border:1px solid #4a6b81!important}
.desk-scout-chips{display:flex;flex-wrap:wrap;gap:6px;margin:9px 0}
.desk-scout-chip{background:#203d53;border:1px solid #4d7b96;border-radius:5px;color:#e1f4ff;display:inline-flex;align-items:center;padding:5px 7px;gap:5px;font-size:11px}
.desk-scout-chip button{border:0;background:transparent;color:#ffb0b0;padding:0 3px;cursor:pointer}
.desk-scout-dialog[hidden],.desk-scout-dialog-shade[hidden]{display:none!important}
.desk-scout-dialog-shade{position:fixed;inset:0;background:#040c15b8;z-index:79}
.desk-scout-dialog{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(730px,calc(100vw - 28px));max-height:min(83vh,770px);overflow-y:auto;z-index:80;background:#14273b;border:1px solid #6b9bb5;box-shadow:0 18px 70px #000b;border-radius:11px;padding:0}
.desk-scout-dialog-header{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;border-bottom:1px solid #36546a}
.desk-scout-dialog-header strong{font-size:17px}
.desk-scout-dialog-close{background:transparent;color:#e5f5ff;border:0;font-size:23px;padding:2px 8px}
.desk-scout-condition-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:17px}
.desk-scout-condition-grid label{display:block!important;margin:0!important;min-width:0;padding:8px 9px;border:1px solid #365268;border-radius:7px;background:#1c344a;color:#c9e1ed;font-size:12px}
.desk-scout-condition-grid label select,.desk-scout-condition-grid label input:not([type=checkbox]){display:block;width:100%;margin-top:6px;background:#11283e;border:1px solid #456e89;color:#f2faff;border-radius:5px;padding:8px}
.desk-scout-condition-grid label:has(input[type=checkbox]){display:flex!important;align-items:center;gap:8px}
.desk-scout-dialog-actions{display:flex;justify-content:space-between;gap:10px;border-top:1px solid #36546a;padding:13px 18px;align-items:center}
.desk-scout-dialog-actions button{padding:9px 13px!important}
.desk-view[data-view="scouting"] .scout-filters{display:block!important;background:none!important;padding:0!important;margin:10px 0!important}
.desk-view[data-view="scouting"] .desk-scout-table-tools{margin-top:5px}
.desk-view[data-view="scouting"] .desk-scout-finance{margin-bottom:12px}
.desk-view[data-view="scouting"] .desk-scout-finance span{padding:7px 12px;font-size:12px}
.desk-view[data-view="scouting"] .desk-scout-finance b{font-size:16px}
@media(max-width:580px){.desk-scout-condition-grid{grid-template-columns:1fr}.desk-scout-searchbar>label{flex:1 1 135px}}

"""

DASHBOARD_JS = r"""
(function(){
  'use strict';
  const source=document.getElementById('desk-screen-source');
  const host=document.getElementById('desk-view-host');
  if(!source||!host||source.dataset.initialized==='1')return;
  const names=['dashboard','inbox','transfers','squad','scouting','shortlist','finances','news','season-setup'];
  const titles={
    dashboard:'Manager overview',inbox:"Manager's Inbox",transfers:'Transfer Centre',
    squad:'Squad planner',scouting:'Scouting',shortlist:'My shortlist',finances:'Club finances',
    news:'Market news','season-setup':'Season setup'
  };
  const views={};
  names.forEach(function(name){
    const pane=document.createElement('section');
    pane.id='desk-view-'+name;
    pane.className='desk-view';
    pane.setAttribute('data-view',name);
    pane.setAttribute('aria-label',titles[name]);
    pane.hidden=true;
    views[name]=pane;
    host.appendChild(pane);
  });
  const redirects={
    overview:'dashboard','overview-anchor':'dashboard',
    recruitment:'scouting','buy-players':'scouting',
    purchases:'transfers','transfer-centre':'transfers',
    'window-summary':'transfers'
  };
  function viewForHash(){
    const key=decodeURIComponent((location.hash||'#dashboard').slice(1));
    return views[key]?key:(redirects[key]||
      (document.body.dataset.windowState==='closed'?'transfers':'dashboard'));
  }
  // Existing server-rendered forms, CSRF fields and buttons are moved, not
  // recreated. This preserves current transfer behaviour and permissions.
  let destination='dashboard';
  Array.from(source.children).forEach(function(node){
    if(node.hasAttribute('data-desk-prestart-shortlist')){
      views.shortlist.appendChild(node);
      return;
    }
    if(node.tagName==='H2'){
      const id=node.id||'';
      const text=(node.textContent||'').trim().toLowerCase();
      if(id==='overview-anchor')destination='dashboard';
      else if(id==='squad')destination='squad';
      else if(id==='recruitment')destination='shortlist';
      else if(id==='scouting')destination='scouting';
      else if(id==='transfer-centre'||id==='window-summary')
        destination='transfers';
      else if(id==='season-setup')destination='season-setup';
      else if(id==='purchases')destination='transfers';
      else if(id==='inbox')destination='inbox';
      else if(text==='market news')destination='news';
    }else if(node.classList&&node.classList.contains('card')&&
       node.textContent&&node.textContent.trim().startsWith("Manager's decisions")){
      destination='inbox';
    }
    views[destination].appendChild(node);
  });
  source.dataset.initialized='1';
  source.hidden=true;

  // The complete shortlist section is routed to its own tab above.
  // Never leave an orphan explanatory panel in Scouting.
  const noticeText='Your shortlist is saved to this career and remains available after the window closes.';
  if(!views.shortlist.children.length){
    views.shortlist.appendChild(emptyPanel('Your shortlist is empty',noticeText));
  }

  function emptyPanel(heading,message){
    const box=document.createElement('div');
    box.className='desk-empty';
    const b=document.createElement('strong');
    b.textContent=heading;
    const p=document.createElement('p');p.textContent=message;
    box.appendChild(b);box.appendChild(p);
    return box;
  }
  const numOffers=Number(document.body.dataset.incomingOffers||0);
  const numUnread=Number(document.body.dataset.unread||0);
  const numSigned=Number(document.body.dataset.signed||0);
  const numSaved=Number(document.body.dataset.saved||0);
  const state=document.body.dataset.windowState||'not_started';

  // Provide a concise, actionable overview with the original financial
  // cards immediately underneath. The figures remain sourced from the server.
  const intro=document.createElement('div');
  intro.className='desk-view-header';
  const titleWrap=document.createElement('div');
  const h2=document.createElement('h2');
  h2.textContent='Your transfer window';
  const desc=document.createElement('p');
  desc.className='muted';
  desc.textContent=state==='open'?
    'Keep on top of offers, negotiations and recruitment before the deadline.':
    state==='closed'?'The window is closed. Review results and registrations.':
    'Review your squad and saved targets before starting the clock.';
  titleWrap.appendChild(h2);titleWrap.appendChild(desc);
  intro.appendChild(titleWrap);
  views.dashboard.insertBefore(intro,views.dashboard.firstChild);
  const quick=document.createElement('div');
  quick.className='desk-actions-bar';
  [
    {label:"Manager's Inbox",description:numOffers+' incoming offers · '+numUnread+' unread',screen:'inbox'},
    {label:'Transfer Centre',description:numSigned+' signed deals · all bids',screen:'transfers'},
    {label:'Scouting',description:'Discover players and evaluate targets',screen:'scouting'}
  ].forEach(function(entry){
    const b=document.createElement('button');
    b.type='button';b.className='desk-action-tile';
    b.setAttribute('data-desk-tab',entry.screen);
    const strong=document.createElement('strong');strong.textContent=entry.label;
    const small=document.createElement('small');small.textContent=entry.description;
    b.appendChild(strong);b.appendChild(small);quick.appendChild(b);
  });
  intro.insertAdjacentElement('afterend',quick);
  if(state==='closed'){
    const next=document.createElement('div');
    next.className='card desk-post-window-next';
    const explanation=document.createElement('strong');
    explanation.textContent='Transfer window complete — your final squads are ready to review';
    const continueLink=document.createElement('a');
    continueLink.href='#season-setup';
    continueLink.dataset.deskTab='season-setup';
    continueLink.textContent='Continue to season setup →';
    next.append(explanation,continueLink);
    quick.insertAdjacentElement('beforebegin',next);
  }

  // Use the authoritative budget breakdown already rendered on the page.
  const budget=document.querySelector('#budget-panel');
  const budgetValues=budget?budget.dataset:document.body.dataset;
  const financeHeading=document.createElement('h2');
  financeHeading.textContent='Current financial position';
  views.finances.appendChild(financeHeading);
  if(budgetValues.feeRemaining!==undefined){
    const grid=document.createElement('div');
    grid.className='desk-finance-grid';
    [
      {name:'Transfer budget',remaining:Number(budgetValues.feeRemaining),
        total:Number(budgetValues.feeTotal),suffix:'available'},
      {name:'Weekly wage headroom',remaining:Number(budgetValues.wageRemaining),
        total:Number(budgetValues.wageTotal),suffix:'per week'}
    ].forEach(function(entry){
      const card=document.createElement('div');card.className='card';
      const label=document.createElement('div');label.className='label';label.textContent=entry.name;
      const val=document.createElement('div');val.className='desk-finance-value';
      val.textContent=gbp(entry.remaining);
      const track=document.createElement('div');track.className='desk-finance-track';
      const fill=document.createElement('div');fill.className='desk-finance-fill';
      fill.style.width=Math.min(100,Math.max(0,entry.remaining/Math.max(1,entry.total)*100))+'%';
      track.appendChild(fill);
      card.appendChild(label);card.appendChild(val);card.appendChild(track);
      grid.appendChild(card);
    });
    views.finances.appendChild(grid);
    const saleNote=document.createElement('p');
    saleNote.className='muted';saleNote.dataset.saleBudgetSummary='';
    saleNote.textContent='Confirmed sales: '+gbp(Number(budgetValues.reinvested)||0)+
      ' made available for new transfers; '+gbp(Number(budgetValues.boardRetained)||0)+
      ' retained by the board (FC27 game-model policy).';
    views.finances.appendChild(saleNote);

  }else{
    views.finances.appendChild(emptyPanel(
      'Budget breakdown is not yet active',
      'The live transfer and wage commitments will appear when the transfer window begins.'
    ));
  }
  function gbp(value){
    const negative=value<0?'-':'';
    value=Math.abs(value);
    return negative+'£'+(value>=1000000?(value/1000000).toFixed(2)+'m':
      value>=1000?Math.round(value/1000)+'k':Math.round(value).toLocaleString('en-GB'));
  }
  if(!views.inbox.children.length)
    views.inbox.appendChild(emptyPanel('No inbox activity','Offers will appear once clubs begin approaching your players.'));
  if(!views.transfers.children.length)
    views.transfers.appendChild(emptyPanel('No transfers underway','Scouting, shortlisting and recruitment are available from the navigation.'));
  if(!views.squad.children.length)
    views.squad.appendChild(emptyPanel('No squad data','Open a career to manage your registered players.'));
  if(!views['season-setup'].children.length)
    views['season-setup'].appendChild(emptyPanel('Season setup opens at the deadline',
      'Complete your transfer window before preparing your PES squads.'));
  if(!views.scouting.children.length)
    views.scouting.appendChild(emptyPanel('Scouting is not active on this screen','You can still open saved scouting profiles from your shortlist.'));

  // Inbox is a compact FM-like message list. Every offer remains a separate
  // message so competing bids are readable and each has its own actions.
  // The original server-validated forms stay inside the expanded message.
  let inboxGrid=views.inbox.querySelector(':scope > .grid');
  if(!inboxGrid){
    inboxGrid=document.createElement('div');
    inboxGrid.className='grid';
    views.inbox.appendChild(inboxGrid);
  }
  inboxGrid.classList.add('desk-inbox-list');
  const inboxLayout=document.createElement('div');
  inboxLayout.className='desk-inbox-split';
  inboxGrid.before(inboxLayout);
  const inboxReader=document.createElement('div');
  inboxReader.className='desk-inbox-reader';
  inboxReader.setAttribute('aria-label','Selected message');
  inboxLayout.append(inboxGrid,inboxReader);
  const inboxCardItems=new WeakMap();
  let selectedInboxCard=null,selectedInboxItem=null,selectedInboxDetail=null;
  function selectInboxCard(card){
    if(!card)return;
    const item=inboxCardItems.get(card);
    if(!item)return;
    if(selectedInboxCard===card)return;
    if(selectedInboxItem&&selectedInboxDetail){
      selectedInboxItem.appendChild(selectedInboxDetail);
      selectedInboxItem.dataset.selected='false';
    }
    selectedInboxCard=card;selectedInboxItem=item;
    selectedInboxDetail=item.querySelector('.desk-inbox-detail');
    item.dataset.selected='true';
    inboxReader.replaceChildren();
    const heading=document.createElement('header');
    heading.className='desk-inbox-reader-header';
    const intro=document.createElement('div');
    const strong=document.createElement('strong');
    strong.textContent=card.dataset.deskPlayerName||'Transfer';
    const small=document.createElement('small');
    small.textContent=cleanInboxClub(card.dataset.deskBuyer||'')+
      ' · '+(inboxLabels[card.dataset.deskStatus]||'Transfer update');
    intro.append(strong,small);heading.appendChild(intro);
    inboxReader.append(heading,selectedInboxDetail);
  }
  const offerCards=Array.from(inboxGrid.querySelectorAll(':scope > .offer[data-desk-player]'));
  const inboxColumns=document.createElement('div');
  inboxColumns.className='desk-inbox-columns';
  for(const label of ['!','Player / subject','Buying club','Fee','Status']){
    const span=document.createElement('span');span.textContent=label;
    inboxColumns.appendChild(span);
  }
  inboxGrid.prepend(inboxColumns);
  let refreshInboxList=()=>{};
  const inboxLabels={
    proposed:'New offer',countered:'Negotiating',
    accepted_pending_contract:'Player/agent talks',
    agreed_future:'Confirmed',completed:'Confirmed',
    withdrawn:'Withdrawn',rejected:'Rejected'
  };
  function cleanInboxClub(value){
    return String(value||'').replace(/\s*\[WH27:[^\]]+\]\s*$/i,'').trim();
  }
  function actionRequired(card){
    return card.dataset.deskStatus==='proposed'||
      (card.dataset.deskStatus==='accepted_pending_contract'&&
       card.dataset.deskAgent==='terms_accepted');
  }
  function refreshInboxItem(card){
    const holder=inboxCardItems.get(card)||card.closest('.desk-inbox-item');
    if(!holder)return;
    const status=card.dataset.deskStatus||'proposed';
    const required=actionRequired(card);
    holder.dataset.actionNeeded=String(required);
    holder.dataset.status=status;
    holder.querySelector('.desk-inbox-flag').textContent=required?'!':'';
    holder.querySelector('.desk-inbox-subject').textContent=
      card.dataset.deskPlayerName||'Player transfer';
    holder.querySelector('.desk-inbox-sender').textContent=
      cleanInboxClub(card.dataset.deskBuyer||'Buying club');
    holder.querySelector('.desk-inbox-fee').textContent=
      card.querySelector('.count')?.textContent.trim()||'—';
    holder.querySelector('.desk-inbox-state').textContent=inboxLabels[status]||status;
  }
  function makeInboxItem(card){
    if(card.closest('.desk-inbox-item'))return;
    const item=document.createElement('details');
    item.className='desk-inbox-item';
    const summary=document.createElement('summary');
    for(const className of ['desk-inbox-flag','desk-inbox-subject',
        'desk-inbox-sender','desk-inbox-fee','desk-inbox-state']){
      const cell=document.createElement('span');
      cell.className=className;summary.appendChild(cell);
    }
    const body=document.createElement('div');
    body.className='desk-inbox-detail';
    card.before(item);
    item.append(summary,body);
    body.appendChild(card);
    inboxCardItems.set(card,item);
    summary.addEventListener('click',function(event){
      event.preventDefault();
      selectInboxCard(card);
    });
    refreshInboxItem(card);
  }
  offerCards.forEach(makeInboxItem);
  if(offerCards.length)selectInboxCard(offerCards[0]);
  else inboxReader.innerHTML='<div class="desk-inbox-reader-empty">Select a message to read it here.</div>';
  if(!offerCards.length)inboxGrid.hidden=true;
  // Fast client-side inbox filters. Refreshing the market fetches genuine
  // updates from Flask, but switching views and narrowing visible cards
  // never needs a page request.
  if(inboxGrid){
    const toolbar=document.createElement('div');
    toolbar.className='desk-inbox-tools';
    let activeFilter='all';
    let playerQuery='';
    const filters=[
      ['all','All offers'],['action','Action needed'],
      ['talks','Negotiating'],['signed','Confirmed'],['closed','Rejected / closed']
    ];
    const filterButtons=[];
    filters.forEach(function(item){
      const button=document.createElement('button');button.type='button';
      button.className='desk-filter-button';button.textContent=item[1];
      button.setAttribute('aria-pressed',item[0]==='all'?'true':'false');
      button.dataset.inboxChoice=item[0];
      button.addEventListener('click',function(){
        activeFilter=item[0];
        filterButtons.forEach(function(b){
          b.setAttribute('aria-pressed',String(b.dataset.inboxChoice===activeFilter));
        });
        applyInboxFilter();
      });
      toolbar.appendChild(button);filterButtons.push(button);
    });
    const search=document.createElement('input');search.type='search';
    search.placeholder='Find a player or buying club';
    search.setAttribute('aria-label','Search incoming offers');
    search.addEventListener('input',function(){
      playerQuery=search.value.trim().toLocaleLowerCase();
      applyInboxFilter();
    });
    toolbar.appendChild(search);
    const reset=document.createElement('button');reset.type='button';
    reset.className='desk-filter-button';reset.textContent='Clear filters';
    reset.addEventListener('click',function(){
      search.value='';playerQuery='';activeFilter='all';
      filterButtons.forEach(function(b){
        b.setAttribute('aria-pressed',String(b.dataset.inboxChoice==='all'));
      });
      applyInboxFilter();
    });
    toolbar.appendChild(reset);
    const inboxH=views.inbox.querySelector('#inbox');
    if(inboxH)inboxH.insertAdjacentElement('afterend',toolbar);
    else views.inbox.insertBefore(toolbar,views.inbox.firstChild);
    function qualifies(card){
      const status=card.dataset.deskStatus;
      const playerState=card.dataset.deskAgent;
      const haystack=((card.dataset.deskPlayerName||'')+' '+
        (card.dataset.deskBuyer||'')).toLocaleLowerCase();
      const matches=(!playerQuery||haystack.includes(playerQuery));
      let statusMatch=true;
      if(activeFilter==='action')
        statusMatch=(status==='proposed'||(
          status==='accepted_pending_contract'&&playerState==='terms_accepted'));
      else if(activeFilter==='talks')
        statusMatch=(status==='countered'||status==='accepted_pending_contract');
      else if(activeFilter==='signed')
        statusMatch=(status==='agreed_future'||status==='completed');
      else if(activeFilter==='closed')
        statusMatch=(status==='withdrawn'||status==='rejected');
      return matches&&statusMatch;
    }
    function applyInboxFilter(){
      offerCards.forEach(function(card){
        const item=inboxCardItems.get(card);
        if(item)item.hidden=!qualifies(card);
      });
      const existing=views.inbox.querySelector('.desk-no-match');
      if(existing)existing.remove();
      if(selectedInboxCard&&!qualifies(selectedInboxCard)){
        selectedInboxCard=null;
        const next=offerCards.find(qualifies);
        if(next)selectInboxCard(next);
        else{
          if(selectedInboxItem&&selectedInboxDetail){
            selectedInboxItem.appendChild(selectedInboxDetail);
            selectedInboxItem.dataset.selected='false';
          }
          selectedInboxItem=null;selectedInboxDetail=null;
          inboxReader.innerHTML='<div class="desk-inbox-reader-empty">No messages match these filters.</div>';
        }
      }else if(!selectedInboxCard){
        const next=offerCards.find(qualifies);
        if(next)selectInboxCard(next);
      }
      if(offerCards.length && !offerCards.some(qualifies)){
        const message=emptyPanel('No offers match',
          'Try another player, buying club or status.');
        message.classList.add('desk-no-match');
        toolbar.insertAdjacentElement('afterend',message);
      }
    }
    refreshInboxList=applyInboxFilter;
    views.inbox.addEventListener('click',function(e){
      const b=e.target.closest('[data-desk-filter-player]');
      if(!b)return;
      playerQuery=b.dataset.deskFilterPlayer.toLocaleLowerCase();
      search.value=b.dataset.deskFilterPlayer;
      activeFilter='all';
      filterButtons.forEach(function(button){
        button.setAttribute('aria-pressed',String(button.dataset.inboxChoice==='all'));
      });
      applyInboxFilter();
    });
  }

  // Sort and narrow the rows that are already visible in this career.
  // Sorting works entirely client-side. Column inputs are immediate; there
  // is no separate Apply Filter step and no extra server-side offer action.
  document.querySelectorAll('.desk-view table').forEach(function(table){
    if(!table.tHead||!table.tBodies.length||!table.tHead.rows.length)return;
    if(table.dataset.deskEnhance==='0')return;
    const head=table.tHead.rows[0];
    const body=table.tBodies[0];
    if(head.cells.length<2)return;
    let sortIndex=-1,sortDirection=1;
    const conditions=new Map();
    const enableColumnSearch=!views.transfers.contains(table);
    const filterRow=document.createElement('tr');
    filterRow.className='desk-table-filter-row';
    function apply(){
      Array.from(body.rows).forEach(function(row){
        let visible=true;
        conditions.forEach(function(query,column){
          if(!query)return;
          const cell=row.cells[column];
          const hay=cell?cell.textContent.toLocaleLowerCase():'';
          if(!hay.includes(query))visible=false;
        });
        row.hidden=!visible;
      });
    }
    Array.from(head.cells).forEach(function(th,index){
      const label=th.textContent.trim();
      if(!label)return;
      const control=document.createElement('button');
      control.type='button';control.className='desk-table-sort';
      control.setAttribute('aria-label','Sort by '+label);
      control.textContent=label;
      th.textContent='';th.appendChild(control);
      const filterCell=document.createElement('th');
      const filter=document.createElement('input');
      filter.type='search';filter.placeholder='⌕';
      filter.setAttribute('aria-label','Filter '+label);
      filter.addEventListener('input',function(){
        conditions.set(index,filter.value.trim().toLocaleLowerCase());
        apply();
      });
      if(enableColumnSearch){
        filterCell.appendChild(filter);
        filterCell.className=th.className;
        filterRow.appendChild(filterCell);
      }
      control.addEventListener('click',function(){
        sortDirection=(sortIndex===index?-sortDirection:1);
        sortIndex=index;
        table.querySelectorAll('.desk-table-sort').forEach(function(b){
          b.removeAttribute('aria-sort');
        });
        control.setAttribute('aria-sort',sortDirection===1?'ascending':'descending');
        const numeric=th.dataset.sortType==='number';
        const sorted=Array.from(body.rows).sort(function(a,b){
          const ca=a.cells[index],cb=b.cells[index];
          const va=ca?.dataset.sortValue||ca?.textContent.trim()||'';
          const vb=cb?.dataset.sortValue||cb?.textContent.trim()||'';
          if(numeric)return sortDirection*(Number(va.replace(/[^\d.-]/g,''))-
                                          Number(vb.replace(/[^\d.-]/g,'')));
          return sortDirection*va.localeCompare(vb,undefined,{numeric:true,sensitivity:'base'});
        });
        sorted.forEach(function(row){body.appendChild(row);});
      });
    });
    if(enableColumnSearch)table.tHead.appendChild(filterRow);
    if(!enableColumnSearch)return;
    Array.from(body.rows).forEach(function(row){
      Array.from(row.cells).forEach(function(cell,index){
        // Clicking a plain position, club, value or status cell acts like
        // selecting its text in that column's quick filter.
        if(cell.querySelector('form,button,a,input,select'))return;
        cell.classList.add('desk-cell-quickfilter');
        cell.title='Click to filter this column';
        cell.addEventListener('click',function(){
          const filter=filterRow.cells[index]?.querySelector('input');
          if(!filter)return;
          filter.value=(cell.textContent||'').trim();
          filter.dispatchEvent(new Event('input',{bubbles:true}));
        });
      });
    });
  });
  // Keep the existing source-backed 17k-player search engine and form
  // serialization, but present conditions in a compact FM-style pop-out.
  const compactForm=views.scouting.querySelector('form.scout-filters');
  if(compactForm){
    const searchBar=document.createElement('div');
    searchBar.className='desk-scout-searchbar';
    compactForm.prepend(searchBar);
    const nameField=compactForm.querySelector('[name="scout_query"]')?.closest('label');
    const sortField=compactForm.querySelector('[name="scout_sort"]')?.closest('label');
    const orderField=compactForm.querySelector('[name="scout_order"]')?.closest('label');
    for(const field of [nameField,sortField,orderField])if(field)searchBar.appendChild(field);
    if(nameField){
      const input=nameField.querySelector('input');
      if(input){input.placeholder='Search all players by name';input.setAttribute('aria-label','Search players');}
    }
    const openButton=document.createElement('button');
    openButton.type='button';openButton.className='desk-scout-add';
    openButton.textContent='+ Add condition';
    openButton.setAttribute('aria-expanded','false');
    searchBar.appendChild(openButton);
    const resetButton=document.createElement('button');
    resetButton.type='button';resetButton.className='desk-scout-clear';
    resetButton.textContent='Clear conditions';
    searchBar.appendChild(resetButton);
    const chips=document.createElement('div');
    chips.className='desk-scout-chips';chips.setAttribute('aria-live','polite');
    searchBar.insertAdjacentElement('afterend',chips);
    const shade=document.createElement('div');shade.className='desk-scout-dialog-shade';
    shade.hidden=true;
    const panel=document.createElement('div');
    panel.className='desk-scout-dialog';panel.hidden=true;
    panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');
    panel.setAttribute('aria-label','Add scouting conditions');
    const header=document.createElement('div');header.className='desk-scout-dialog-header';
    const title=document.createElement('strong');title.textContent='Add scouting conditions';
    const closeButton=document.createElement('button');
    closeButton.type='button';closeButton.className='desk-scout-dialog-close';
    closeButton.setAttribute('aria-label','Close conditions');closeButton.textContent='×';
    header.append(title,closeButton);panel.append(header);
    const grid=document.createElement('div');grid.className='desk-scout-condition-grid';
    const conditionFields=Array.from(compactForm.children).filter(
      child=>child.tagName==='LABEL'&&child!==nameField&&
          child!==sortField&&child!==orderField);
    const available=[];
    for(const field of conditionFields){
      grid.appendChild(field);
      const input=field.querySelector('[name]');
      if(input)available.push({input,field,name:input.name});
    }
    const budgetControl=compactForm.querySelector('[data-scout-budget]');
    if(budgetControl){budgetControl.type='button';grid.appendChild(budgetControl);}
    panel.appendChild(grid);
    const actions=document.createElement('div');actions.className='desk-scout-dialog-actions';
    const context=document.createElement('small');
    context.textContent='Conditions combine to narrow the player list.';
    const done=document.createElement('button');
    done.type='button';done.className='desk-scout-add';done.textContent='Show results';
    actions.append(context,done);panel.append(actions);
    // The old visible submit button is redundant: instant AJAX filtering
    // and this explicit Show results action continue to use the same form.
    Array.from(compactForm.querySelectorAll(':scope > button')).forEach(button=>{
      if(button!==openButton&&button!==resetButton&&button!==budgetControl)
        button.hidden=true;
    });
    compactForm.append(shade,panel);
    function closePanel(){
      shade.hidden=true;panel.hidden=true;
      openButton.setAttribute('aria-expanded','false');
      openButton.focus();
    }
    function showPanel(){
      shade.hidden=false;panel.hidden=false;
      openButton.setAttribute('aria-expanded','true');
      const first=panel.querySelector('input,select');
      first?.focus();
    }
    openButton.addEventListener('click',()=>{
      if(panel.hidden)showPanel();else closePanel();
    });
    closeButton.addEventListener('click',closePanel);
    shade.addEventListener('click',closePanel);
    document.addEventListener('keydown',event=>{
      if(event.key==='Escape'&&!panel.hidden)closePanel();
    });
    done.addEventListener('click',()=>{compactForm.requestSubmit();closePanel();});
    const description={
      scout_position:'Position',scout_min_overall:'Minimum rating',
      scout_max_age:'Maximum age',scout_max_value:'Transfer value',
      scout_max_wage:'Weekly wages',scout_interest:'Would consider move',
      scout_free_only:'Free agents',scout_category:'Rating category',
      scout_min_category:'Minimum category',scout_attribute:'Attribute',
      scout_min_attribute:'Minimum attribute',scout_contract:'Contract',
      scout_squad:'My squad',scout_shortlist:'Shortlist'
    };
    function hasCondition(input){
      return input.type==='checkbox'?input.checked:
        input.value!==''&&input.value!==null;
    }
    function removeCondition(input){
      if(input.type==='checkbox')input.checked=false;
      else input.value='';
      compactForm.requestSubmit();renderChips();
    }
    function renderChips(){
      chips.replaceChildren();
      for(const {input,name} of available){
        if(!hasCondition(input))continue;
        const chip=document.createElement('span');chip.className='desk-scout-chip';
        const label=document.createElement('span');
        const activeValue=input.type==='checkbox'?'':(
          input.tagName==='SELECT'?input.selectedOptions[0]?.textContent:
            input.name==='scout_max_value'||input.name==='scout_max_wage'?
              '£'+Number(input.value).toLocaleString('en-GB'):input.value);
        label.textContent=(description[name]||name.replace('scout_','').replaceAll('_',' '))+
          (activeValue?' · '+activeValue:'');
        const remove=document.createElement('button');remove.type='button';
        remove.textContent='×';remove.setAttribute('aria-label','Remove '+label.textContent);
        remove.addEventListener('click',()=>removeCondition(input));
        chip.append(label,remove);chips.appendChild(chip);
      }
      openButton.textContent='+ Add condition'+(chips.children.length?
        ' ('+chips.children.length+')':'');
    }
    compactForm.addEventListener('change',renderChips);
    compactForm.addEventListener('input',renderChips);
    resetButton.addEventListener('click',()=>{
      available.forEach(({input})=>{
        if(input.type==='checkbox')input.checked=false;else input.value='';
      });
      compactForm.requestSubmit();renderChips();
    });
    const explanation=views.scouting.querySelector('.desk-scout-finance + p.muted');
    if(explanation)explanation.hidden=true;
    renderChips();
  }

  // Server-backed infinite scrolling: no Next button, no 80-player cap,
  // no full Career Desk reload and no duplicate market tick on filter changes.
  const scoutForm=views.scouting.querySelector('form.scout-filters');
  const scoutTable=views.scouting.querySelector('table[data-scout-results]');
  const scoutProgress=views.scouting.querySelector('[data-scout-progress]');
  if(scoutForm&&scoutTable&&scoutProgress){
    const tableBody=scoutTable.tBodies[0];
    const attributesToggle=views.scouting.querySelector('[data-scout-attributes-toggle]');
    if(attributesToggle){
      attributesToggle.addEventListener('click',function(){
        const expanded=scoutTable.classList.toggle('desk-show-attributes');
        attributesToggle.setAttribute('aria-expanded',String(expanded));
        attributesToggle.textContent=expanded?'Hide attributes':'Show attributes';
      });
    }
    const counter=scoutProgress.querySelector('[data-scout-count]');
    const status=scoutProgress.querySelector('[data-scout-loading]');
    const limitControl=scoutForm.querySelector('[data-scout-budget]');
    const valueControl=scoutForm.querySelector('[name="scout_max_value"]');
    let page=1;
    let shown=tableBody.rows.length;
    let total=Number((scoutProgress.dataset.total||'').replace(/,/g,''))||0;
    let hasMore=shown<total;
    let generation=0,active=null;
    const feedUrl=window.location.pathname+'/scout-feed';
    function display(v){return v===null||v===undefined||v===''?'—':String(v);}
    function appendRows(players){
      const fragment=document.createDocumentFragment();
      players.forEach(function(player){
        const row=document.createElement('tr');
        if(player.owned)row.className='owned';
        const first=document.createElement('td');
        const link=document.createElement('a');
        link.href=window.location.pathname+'/player/'+encodeURIComponent(player.player_id);
        link.textContent=player.name;
        first.appendChild(link);
        if(player.shortlisted)first.appendChild(document.createTextNode(' ★'));
        row.appendChild(first);
        const fields=[player.club,player.position,player.overall,player.age,
          player.value,player.wage,player.contract,player.years_left,player.pace,
          player.shooting,player.passing,player.dribbling,
          player.defending,player.physicality];
        if(scoutForm.elements.scout_attribute.value)
          fields.push(player.detail_attribute);
        fields.forEach(function(value,index){
          const cell=document.createElement('td');
          cell.textContent=display(value);
          if(index>=8&&index<=13)cell.className='desk-scout-extra';
          if(index===5)cell.title=player.club==='Free agent'?
            'Reference game wage, not confirmed agent demand':
            'Current game wage, not future agent demand';
          row.appendChild(cell);
        });
        fragment.appendChild(row);
      });
      tableBody.appendChild(fragment);
    }
    async function loadScout(reset){
      if(reset){
        generation++;
        if(active)active.abort();
        active=null;
        page=0;shown=0;hasMore=true;
        status.textContent='Applying filters…';
        const search=new URLSearchParams(new FormData(scoutForm));
        history.replaceState(null,'',window.location.pathname+'?'+
          search.toString()+'#scouting');
      }
      if(active||!hasMore)return;
      const requestId=generation;
      const next=page+1;
      const params=new URLSearchParams(new FormData(scoutForm));
      params.set('scout_page',String(next));
      const controller=new AbortController();
      active=controller;
      status.textContent='Loading players…';
      try{
        const response=await fetch(feedUrl+'?'+params.toString(),{
          credentials:'same-origin',cache:'no-store',
          headers:{'Accept':'application/json'},signal:controller.signal});
        if(response.status===410||response.status===404){
          window.location.assign('/world/play?error='+encodeURIComponent(
            'This test career is no longer on the server following a deployment. Please create a new career.'));
          return;
        }
        if(!response.ok){
          const detail=await response.json().catch(()=>null);
          throw new Error((detail&&detail.detail)||'Scouting feed unavailable');
        }
        const data=await response.json();
        if(requestId!==generation)return;
        if(reset)tableBody.replaceChildren();
        appendRows(data.players);
        shown+=data.players.length;
        total=data.total;
        page=next;hasMore=Boolean(data.has_more);
        counter.textContent='Showing '+shown.toLocaleString('en-GB')+
          ' of '+total.toLocaleString('en-GB')+' players';
        status.textContent=hasMore?'Scroll to see more players':
          (total===0?'No players match these filters':'All matching players loaded');
      }catch(error){
        if(error.name==='AbortError')return;
        if(requestId===generation)status.textContent=
          'Unable to load players: '+String(error.message||error)+
          '. Change a filter to retry.';
      }finally{
        if(active===controller)active=null;
      }
    }
    if(limitControl&&valueControl){
      limitControl.addEventListener('click',function(){
        valueControl.value=String(Math.max(0,Math.floor(
          Number(document.body.dataset.feeRemaining)||0)));
        scoutForm.requestSubmit();
      });
    }
    scoutForm.addEventListener('submit',function(event){
      event.preventDefault();
      loadScout(true);
    });
    scoutForm.addEventListener('change',function(event){
      if(event.target.matches('select,input[type=checkbox]'))
        scoutForm.requestSubmit();
    });
    let searchTimer;
    scoutForm.querySelectorAll('input[type=text],input:not([type]),input[type=number]')
      .forEach(function(input){
        input.addEventListener('input',function(){
          clearTimeout(searchTimer);
          searchTimer=setTimeout(function(){
            if(input.value===''||input.value.length>=2)scoutForm.requestSubmit();
          },550);
        });
      });
    const applyButton=Array.from(scoutForm.querySelectorAll('button')).find(
      function(button){return /apply filter|search players|filter/i.test(button.textContent);}
    );
    if(applyButton)applyButton.hidden=true;
    if('IntersectionObserver' in window){
      const observer=new IntersectionObserver(function(entries){
        if(entries.some(function(entry){return entry.isIntersecting;}))
          loadScout(false);
      },{rootMargin:'500px'});
      observer.observe(scoutProgress);
    }else{
      window.addEventListener('scroll',function(){
        const box=scoutProgress.getBoundingClientRect();
        if(!views.scouting.hidden&&box.top<window.innerHeight+500)
          loadScout(false);
      });
    }
  }

  // Opening Inbox acknowledges server-side unread messages. This is a
  // proper CSRF-protected POST, not a client-only fake badge change.
  // The existing form remains usable without JavaScript.
  let inboxMarkInProgress=false;
  function markInboxViewed(){
    if(Number(document.body.dataset.unread||0)<=0||inboxMarkInProgress)return;
    const form=views.inbox.querySelector('form[data-mark-inbox-read]');
    if(!form)return;
    inboxMarkInProgress=true;
    fetch(form.action,{method:'POST',body:new FormData(form),
      credentials:'same-origin',headers:{'Accept':'application/json'}})
      .then(function(response){
        if(!response.ok)throw new Error('Inbox unread acknowledgement failed');
        return response.json();
      })
      .then(function(result){
        if(!result.ok)return;
        document.body.dataset.unread='0';
        document.querySelectorAll('[data-desk-tab="inbox"] .desk-nav-count')
          .forEach(function(badge){badge.remove();});
        document.querySelectorAll('[data-inbox-unread-label]')
          .forEach(function(item){item.textContent='0';});
        const desc=views.dashboard.querySelector('[data-desk-tab="inbox"] small');
        if(desc)desc.textContent=numOffers+' incoming offers · 0 unread';
        // Keep the POST capability when a NEW bid arrives after this visit.
        form.hidden=true;
      })
      .catch(function(){/* Keep badge if server did not confirm the POST. */})
      .finally(function(){inboxMarkInProgress=false;});
  }

  // Live transfer bids arrive on the authenticated market heartbeat.
  // Never wait for a full page refresh: by that time the 30-minute window
  // may have expired and the manager cannot act.
  const stream=views.inbox.querySelector('#desk-live-offer-stream');
  const outgoing=views.transfers.querySelector('table[data-desk-table="outgoing"]');
  const seen=new Set(Array.from(views.inbox.querySelectorAll('[data-live-offer-id]'),
      el=>Number(el.dataset.liveOfferId)));
  const pound=n=>{
    n=Number(n)||0;const abs=Math.abs(n);
    return (n<0?'-':'')+'£'+(abs>=1e6?(abs/1e6).toFixed(2)+'m':
      abs>=1e3?Math.round(abs/1e3)+'k':Math.round(abs).toLocaleString('en-GB'));
  };
  function updateSaleBudgetUI(result){
    if(result.available_transfer_budget===undefined)return;
    const available=Number(result.available_transfer_budget)||0;
    const total=Number(result.total_transfer_budget)||0;
    const panel=document.querySelector('#budget-panel');
    if(panel){
      panel.dataset.feeRemaining=String(available);
      panel.dataset.feeTotal=String(total);
      panel.dataset.reinvested=String(result.sale_budget_allocated||0);
      panel.dataset.boardRetained=String(result.sale_board_withheld||0);
      const label=panel.querySelector('#fee-current');
      if(label)label.textContent=pound(available);
      const bar=panel.querySelector('#fee-bar');
      if(bar)bar.style.width=Math.min(100,Math.max(0,available/Math.max(1,total)*100))+'%';
    }
    document.body.dataset.feeRemaining=String(available);
    document.body.dataset.feeTotal=String(total);
    const scoutValue=views.scouting.querySelector('.desk-scout-finance b');
    if(scoutValue)scoutValue.textContent=pound(available);
    const financeTile=views.finances.querySelector('.desk-finance-grid .card');
    if(financeTile){
      const number=financeTile.querySelector('.desk-finance-value');
      if(number)number.textContent=pound(available);
      const fill=financeTile.querySelector('.desk-finance-fill');
      if(fill)fill.style.width=Math.min(100,Math.max(0,available/Math.max(1,total)*100))+'%';
    }
    const note=views.finances.querySelector('[data-sale-budget-summary]');
    if(note)note.textContent='Confirmed sales: '+
      pound(result.sale_budget_allocated||0)+' made available for new transfers; '+
      pound(result.sale_board_withheld||0)+' retained by the board.';
  }
  window.fc27UpdateBudget=updateSaleBudgetUI;
  const labels={
    proposed:'New offer',countered:'Awaiting buyer',
    accepted_pending_contract:'Player/agent talks',
    agreed_future:'Confirmed',
    completed:'Confirmed',
    withdrawn:'Withdrawn',rejected:'Declined'
  };
  function formFor(offer,verb,csrf){
    const form=document.createElement('form');
    form.method='post';
    form.action=location.pathname+'/decision';
    for(const [name,value] of [['csrf',csrf],['offer_id',offer.offer_id]]){
      const input=document.createElement('input');
      input.type='hidden';input.name=name;input.value=String(value);
      form.appendChild(input);
    }
    if(verb==='counter'){
      const label=document.createElement('label');
      label.textContent='Asking fee (£) ';
      const input=document.createElement('input');
      input.type='number';input.name='counter_fee';
      input.min=String(Number(offer.fee)+1);
      input.max=String(Math.min(Number(offer.fee)*2,1000000000));
      input.value=String(Math.min(Math.floor(Number(offer.fee)*1.10),1000000000));
      input.required=true;label.appendChild(input);form.appendChild(label);
    }
    const btn=document.createElement('button');
    btn.name='decision';btn.value=verb;
    btn.textContent=verb==='accept'?'Accept fee':
      verb==='reject'?'Reject':
      verb==='finalise'?'Finalise transfer':
      verb==='cancel'?'Cancel transfer':
      verb==='delay'?'Request more time':'Counter';
    if(verb==='reject'||verb==='cancel')btn.className='danger';
    form.appendChild(btn);return form;
  }
  function alertOfNewOffer(offer){
    if(!views.inbox.hidden)return;
    let toast=document.getElementById('desk-offer-toast');
    if(!toast){
      toast=document.createElement('button');
      toast.id='desk-offer-toast';toast.type='button';
      toast.className='desk-offer-toast';toast.dataset.deskTab='inbox';
      document.body.appendChild(toast);
    }
    toast.textContent='New bid: '+offer.player+' · '+pound(offer.fee)+
      ' · Open Inbox to respond';
  }
  function showDecisionFeedback(card,message,error){
    if(!card)return;
    let p=card.querySelector('[data-decision-feedback]');
    if(!p){
      p=document.createElement('p');
      p.className='desk-decision-feedback';
      p.dataset.decisionFeedback='';
      card.appendChild(p);
    }
    p.dataset.error=error?'1':'0';
    p.textContent=message;
  }
  function updateIncomingCard(offer,csrf){
    const id=Number(offer.offer_id);
    const status=offer.status;
    const agent=offer.agent_status;
    for(const card of views.inbox.querySelectorAll('[data-live-offer-id="'+id+'"]')){
      card.dataset.deskStatus=status;
      if(agent!==null && agent!==undefined)card.dataset.deskAgent=agent;
      refreshInboxItem(card);
      refreshInboxList();
      const label=card.querySelector('.label');
      if(label)label.textContent=(card.dataset.deskBuyer||offer.buyer||'Buying club')+
        ' · '+(labels[status]||status);
      if(status==='proposed')continue;
      let actions=card.querySelector('.actions');
      if(actions){
        // Never leave stale Accept buttons usable after an authoritative
        // decision; the server still validates every status and deadline.
        for(const form of actions.querySelectorAll('form[action$="/market/decision"]')){
          const verbs=Array.from(form.querySelectorAll('button[name="decision"]'),
            button=>button.value);
          const allowed=status==='accepted_pending_contract'?
            (agent==='terms_accepted'?['finalise','cancel','delay']:['cancel']):
            status==='countered'?['cancel']:[];
          if(!verbs.some(v=>allowed.includes(v)))form.remove();
        }
      }
      const needsActions=status==='countered'||status==='accepted_pending_contract';
      if(needsActions){
        if(!actions){
          actions=document.createElement('div');
          actions.className='actions';
          card.appendChild(actions);
        }
        const values=Array.from(actions.querySelectorAll('button[name="decision"]'),
          button=>button.value);
        if(status==='accepted_pending_contract'&&agent==='terms_accepted'&&
           !values.includes('finalise'))
          actions.prepend(formFor(offer,'finalise',csrf));
        if(!values.includes('cancel'))actions.appendChild(formFor(offer,'cancel',csrf));
      }
      let note=card.querySelector('[data-inline-agent-note]');
      if(!note){
        note=document.createElement('p');
        note.className='desk-inline-agent-note';note.dataset.inlineAgentNote='';
        card.appendChild(note);
      }
      note.textContent=status==='accepted_pending_contract'?
        (agent==='terms_accepted'?
          'Player and agent terms agreed — finalise the transfer before the deadline.':
          'Fee accepted — player/agent talks are in progress.'):
        status==='countered'?'Counter sent — awaiting the buying club.':
        status==='agreed_future'?'Confirmed — registration will take place at the deadline.':
        status==='rejected'?'Offer rejected.':
        status==='withdrawn'?'Negotiation withdrawn.':
        status==='completed'?'Transfer registered.':'';
    }
  }
  function updateOfferRow(offer){
    if(!outgoing)return;
    const row=outgoing.tBodies[0].querySelector(
      '[data-live-offer-id="'+Number(offer.offer_id)+'"]');
    if(row&&row.cells.length>3){
      row.cells[3].textContent=labels[offer.status]||offer.status;
      if(row.cells[4] && !['proposed','countered','accepted_pending_contract'].includes(offer.status))
        row.cells[4].replaceChildren();
    }
  }
  // A buying-club decision uses the same server-side agent and transfer
  // checks as the native form, but refreshes ONLY the affected buying card.
  // This avoids rebuilding the 17,593-player dashboard after every wage or
  // seller-counter click.
  document.addEventListener('submit',async function(event){
    const form=event.target;
    if(!(form instanceof HTMLFormElement)||!views.transfers.contains(form)||
       form.classList.contains('desk-transfer-cancel-form'))return;
    const buyingAction=form.action.endsWith('/market/buy/decision');
    const rebid=form.action.endsWith('/market/buy/rebid');
    if(!buyingAction&&!rebid)return;
    event.preventDefault();
    if(form.dataset.saving==='1')return;
    const submit=event.submitter;
    const data=new FormData(form);
    if(buyingAction&&submit?.name==='decision')
      data.set('decision',submit.value);
    const oldCard=form.closest('[data-buy-offer-id]');
    const host=oldCard?.parentElement;
    const buttons=Array.from(form.querySelectorAll('button'));
    const status=document.createElement('p');
    status.className='desk-decision-feedback';
    status.setAttribute('role','status');
    status.textContent='Saving negotiation…';
    oldCard?.appendChild(status);
    form.dataset.saving='1';buttons.forEach(b=>b.disabled=true);
    try{
      const response=await fetch(form.action,{method:'POST',body:data,
        headers:{'Accept':'application/json'},credentials:'same-origin',
        cache:'no-store'});
      const result=await response.json().catch(()=>null);
      if(!response.ok||!result?.ok)
        throw new Error(result?.error||'Negotiation could not be saved');
      const template=document.createElement('template');
      template.innerHTML=result.html||'';
      const newCard=template.content.querySelector('[data-buy-offer-id]');
      if(!newCard)throw new Error('Saved, but updated negotiation card is unavailable');
      if(rebid){
        host?.prepend(newCard);
        status.textContent=result.message;
      }else{
        oldCard?.replaceWith(newCard);
        const info=document.createElement('p');
        info.className='desk-decision-feedback';
        info.setAttribute('role','status');info.textContent=result.message;
        newCard.appendChild(info);
      }
      const table=views.transfers.querySelector('[data-desk-table="incoming"]');
      if(table){
        let row=table.tBodies[0].querySelector(
          '[data-buy-offer-id="'+result.offer_id+'"]');
        if(!row){
          row=document.createElement('tr');
          row.dataset.buyOfferId=String(result.offer_id);
          for(let i=0;i<5;i++)row.appendChild(document.createElement('td'));
          table.tBodies[0].prepend(row);
        }
        row.cells[0].textContent=result.player_name;
        row.cells[1].textContent=result.seller_name;
        row.cells[2].textContent=pound(result.offered_fee);
        row.cells[2].dataset.sortValue=String(result.offered_fee);
        row.cells[3].textContent=result.status_label;
        row.cells[4].replaceChildren();
        if(['proposed','countered','accepted_pending_contract'].includes(result.status)){
          const cancel=document.createElement('form');
          cancel.method='post';cancel.action=location.pathname+'/buy/decision';
          cancel.className='desk-transfer-cancel-form';
          for(const [name,value] of [['csrf',data.get('csrf')],
              ['offer_id',result.offer_id]]){
            const input=document.createElement('input');
            input.type='hidden';input.name=name;input.value=String(value);
            cancel.appendChild(input);
          }
          const btn=document.createElement('button');
          btn.name='decision';btn.value='withdraw';btn.className='desk-transfer-cancel';
          btn.textContent='×';btn.title='Withdraw unsigned offer for '+result.player_name;
          btn.setAttribute('aria-label',btn.title);
          cancel.appendChild(btn);row.cells[4].appendChild(cancel);
        }
        updateSaleBudgetUI(result);
        const count=table.closest('.desk-transfer-section')
           ?.querySelector('.desk-section-count');
        if(count)count.textContent=String(table.tBodies[0].rows.length);
      }
    }catch(error){
      status.textContent=String(error.message||error);
      status.dataset.error='1';
    }finally{
      form.dataset.saving='0';
      buttons.forEach(b=>{if(b.isConnected)b.disabled=false});
    }
  },true);
  // The browser submits every human Inbox decision via the existing secure,
  // server-validated endpoint, but avoids downloading/re-rendering all 659
  // clubs and 17,593 players after an ordinary Accept/Reject/Counter click.
  // Native POST+redirect remains the fallback when JavaScript is disabled.
  document.addEventListener('submit',async function(event){
    const form=event.target;
    if(!(form instanceof HTMLFormElement)||!views.inbox.contains(form)||
       !form.action.endsWith('/market/decision'))return;
    const button=event.submitter;
    if(!button||!button.name||button.name!=='decision')return;
    event.preventDefault();
    if(form.dataset.saving==='1')return;
    const data=new FormData(form);
    data.set('decision',button.value);
    const id=Number(data.get('offer_id'));
    const card=form.closest('[data-live-offer-id]');
    form.dataset.saving='1';
    const buttons=Array.from(form.querySelectorAll('button'));
    buttons.forEach(b=>b.disabled=true);
    showDecisionFeedback(card,'Saving your '+button.value+' decision…',false);
    try{
      const response=await fetch(form.action,{
        method:'POST',body:data,credentials:'same-origin',
        headers:{'Accept':'application/json'},cache:'no-store'
      });
      const result=await response.json().catch(()=>null);
      if(!response.ok||!result?.ok)
        throw new Error(result?.error||'The decision could not be saved. Please retry.');
      const offer={offer_id:id,status:result.status,
        agent_status:null,buyer:card?.dataset.deskBuyer};
      updateIncomingCard(offer,String(data.get('csrf')||''));
      updateOfferRow(offer);
      updateSaleBudgetUI(result);
      showDecisionFeedback(card,result.message,false);
      if(Number.isFinite(Number(result.unread))){
        document.body.dataset.unread=String(result.unread);
        document.querySelectorAll('[data-desk-tab="inbox"] .desk-nav-count')
          .forEach(badge=>{
            if(!Number(result.unread))badge.remove();
            else badge.textContent=String(result.unread);
          });
      }
    }catch(error){
      showDecisionFeedback(card,String(error.message||error),true);
    }finally{
      form.dataset.saving='0';
      buttons.forEach(b=>{if(b.isConnected)b.disabled=false;});
    }
  },true);
  // Inline X cancels only unsigned deals. Keep the Transfer Centre open,
  // use the authoritative POST/CSRF routes, and update the exact affected row.
  document.addEventListener('submit',async function(event){
    const form=event.target;
    if(!(form instanceof HTMLFormElement)||
       !form.classList.contains('desk-transfer-cancel-form'))return;
    event.preventDefault();
    if(form.dataset.saving==='1')return;
    form.dataset.saving='1';
    const button=event.submitter||form.querySelector('button');
    if(button)button.disabled=true;
    const row=form.closest('tr');
    const action=event.submitter?.value||button?.value||'';
    const data=new FormData(form);
    if(button&&button.name)data.set(button.name,action);
    try{
      const response=await fetch(form.action,{
        method:'POST',body:data,credentials:'same-origin',cache:'no-store',
        headers:{Accept:'application/json'}
      });
      const result=await response.json().catch(()=>null);
      if(!response.ok||!result?.ok)
        throw new Error(result?.error||'Cancellation could not be completed');
      if(row){
        const free=Boolean(row.dataset.freeAgentSigningId);
        const status=free?'Cancelled':labels[result.status]||'Withdrawn';
        if(row.cells[3])row.cells[3].textContent=
          (free?status+' · '+row.cells[3].textContent.split(' · ').slice(1).join(' · '):status);
        if(row.cells[4])row.cells[4].replaceChildren();
        row.dataset.cancelled='true';
      }
      if(!row?.dataset.freeAgentSigningId){
        const id=Number(data.get('offer_id'));
        if(Number.isFinite(id)){
          const offer={offer_id:id,status:result.status||'withdrawn',agent_status:null};
          updateIncomingCard(offer,String(data.get('csrf')||''));
          updateOfferRow(offer);
          if(row?.dataset.buyOfferId&&result.html){
            const html=document.createElement('template');
            html.innerHTML=result.html;
            const card=html.content.querySelector('[data-buy-offer-id]');
            const existing=views.transfers.querySelector(
              '.grid [data-buy-offer-id="'+id+'"]');
            if(card&&existing)existing.replaceWith(card);
          }
        }
      }
      updateSaleBudgetUI(result);
    }catch(error){
      let feedback=row?.querySelector('.desk-transfer-cancel-error');
      if(!feedback&&row?.cells[4]){
        feedback=document.createElement('small');
        feedback.className='desk-transfer-cancel-error';
        row.cells[4].appendChild(feedback);
      }
      if(feedback)feedback.textContent=String(error.message||error);
      if(button)button.disabled=false;
    }finally{form.dataset.saving='0';}
  },true);
  window.fc27SyncIncomingOffers=function(items,csrf){
    if(!Array.isArray(items))return;
    for(const o of items.slice().reverse()){
      const id=Number(o.offer_id);
      if(!Number.isSafeInteger(id)||id<=0)continue;
      if(!seen.has(id)&&inboxGrid){
        seen.add(id);
        const card=document.createElement('div');
        card.className='card offer';card.dataset.liveOfferId=String(id);
        card.dataset.deskPlayer=String(o.player_id);
        card.dataset.deskPlayerName=o.player;card.dataset.deskStatus=o.status;
        card.dataset.deskBuyer=o.buyer;
        const label=document.createElement('div');
        label.className='label';
        label.textContent=o.buyer+' · '+(labels[o.status]||o.status);
        const heading=document.createElement('h3');
        heading.textContent=o.player;
        const amount=document.createElement('div');
        amount.className='count';amount.textContent=pound(o.fee);
        const time=document.createElement('p');time.className='muted';
        time.textContent='Received '+String(o.received_at||'').slice(11,16)+' UTC';
        card.append(label,heading,amount,time);
        if(o.status==='proposed'){
          const actions=document.createElement('div');actions.className='actions';
          for(const verb of ['accept','reject','counter'])
            actions.appendChild(formFor(o,verb,csrf));
          card.appendChild(actions);
          alertOfNewOffer(o);
        }else{
          const note=document.createElement('p');note.className='muted';
          note.textContent='Open the updated Inbox for further negotiation details.';
          card.appendChild(note);
        }
        inboxGrid.hidden=false;
        inboxGrid.insertBefore(card,inboxColumns.nextSibling);
        offerCards.push(card);
        makeInboxItem(card);
        if(!selectedInboxCard)selectInboxCard(card);
        refreshInboxList();
        const empty=views.inbox.querySelector('#desk-inbox-no-offers');
        if(empty)empty.hidden=true;
      }
      updateIncomingCard(o,csrf);
      if(outgoing){
        const tableBody=outgoing.tBodies[0];
        let row=Array.from(tableBody.querySelectorAll('[data-live-offer-id]'))
          .find(el=>Number(el.dataset.liveOfferId)===id);
        if(!row){
          row=document.createElement('tr');row.dataset.liveOfferId=String(id);
          for(let k=0;k<5;k++)row.appendChild(document.createElement('td'));
          tableBody.prepend(row);
        }
        row.cells[0].textContent=o.player;row.cells[1].textContent=o.buyer;
        row.cells[2].textContent=pound(o.fee);
        row.cells[2].dataset.sortValue=String(o.fee);
        row.cells[3].textContent=labels[o.status]||o.status;
        row.cells[4].replaceChildren();
        if(['proposed','countered','accepted_pending_contract'].includes(o.status)){
          const form=formFor(o,'cancel',csrf);
          form.className='desk-transfer-cancel-form';
          const button=form.querySelector('button');
          button.className='desk-transfer-cancel';
          button.textContent='×';
          button.setAttribute('title','Cancel unsigned transfer for '+o.player);
          button.setAttribute('aria-label','Cancel unsigned transfer for '+o.player);
          row.cells[4].appendChild(form);
        }
      }
    }
    const n=outgoing?.tBodies[0].rows.length||0;
    document.body.dataset.incomingOffers=String(n);
    const count=outgoing?.closest('.desk-transfer-section')
      ?.querySelector('.desk-section-count');
    if(count)count.textContent=String(n);
    let mark=views.inbox.querySelector('form[data-mark-inbox-read]');
    if(!mark&&Number(document.body.dataset.unread||0)>0&&csrf){
      // The Inbox initially has NO mark-read form when no bids exist.
      // A new mid-window offer must still be acknowledged on first opening.
      mark=document.createElement('form');
      mark.method='post';mark.action=location.pathname+'/read';
      mark.setAttribute('data-mark-inbox-read','');
      const field=document.createElement('input');
      field.type='hidden';field.name='csrf';field.value=String(csrf);
      const button=document.createElement('button');
      button.textContent='Mark as read';button.type='submit';
      mark.append(field,button);
      views.inbox.querySelector('#inbox')?.insertAdjacentElement('afterend',mark);
    }
    if(mark&&Number(document.body.dataset.unread||0)>0)mark.hidden=false;
    const badgeText=views.dashboard.querySelector('[data-desk-tab="inbox"] small');
    if(badgeText)badgeText.textContent=n+' incoming offers · '+
      (Number(document.body.dataset.unread)||0)+' unread';
  };

  // Compact squad management uses the same validated manager instructions
  // as the previous page, without paying for a full scouting dashboard reload.
  const squadPanel=views.squad;
  const squadNotice=squadPanel.querySelector('[data-squad-list-feedback]');
  squadPanel.addEventListener('submit',async function(event){
    const form=event.target;
    // An input/button named "action" shadows HTMLFormElement.action.
    // Use the literal URL attribute, as with the free-agent forms.
    if(!(form instanceof HTMLFormElement)||
       !(form.getAttribute('action')||'').endsWith('/market/squad/decision'))return;
    const submit=event.submitter;
    if(!submit||submit.name!=='action')return;
    event.preventDefault();
    if(form.dataset.saving==='1')return;
    const data=new FormData(form);
    data.set('action',submit.value);
    form.dataset.saving='1';
    const buttons=Array.from(form.querySelectorAll('button'));
    buttons.forEach(b=>b.disabled=true);
    if(squadNotice){
      squadNotice.hidden=false;
      squadNotice.textContent='Saving squad instruction…';
      squadNotice.style.color='#b9eccc';
    }
    try{
      const res=await fetch(form.getAttribute('action'),{method:'POST',body:data,
        credentials:'same-origin',headers:{Accept:'application/json'},cache:'no-store'});
      const result=await res.json().catch(()=>null);
      if(!res.ok||!result?.ok)throw new Error(result?.error||'Squad instruction was not saved');
      const line=form.closest('tr');
      const checkbox=line?.querySelector('input[name="listed"]');
      const description=checkbox?.closest('label')?.querySelector('span');
      if(description)description.textContent=result.listed?'Listed':'Available';
      if(squadNotice)squadNotice.textContent=result.message;
    }catch(error){
      if(squadNotice){
        squadNotice.textContent=String(error.message||error);
        squadNotice.style.color='#ffb6aa';
      }
    }finally{
      form.dataset.saving='0';
      buttons.forEach(b=>{if(b.isConnected)b.disabled=false;});
    }
  },true);

  const squadModeButtons=Array.from(squadPanel.querySelectorAll('[data-squad-mode]'));
  const squadListPane=squadPanel.querySelector('[data-squad-pane="list"]');
  const squadTacticsPane=squadPanel.querySelector('[data-squad-pane="tactics"]');
  function showSquadMode(mode){
    if(squadListPane)squadListPane.hidden=mode!=='list';
    if(squadTacticsPane)squadTacticsPane.hidden=mode!=='tactics';
    squadModeButtons.forEach(b=>b.setAttribute('aria-pressed',String(
      b.dataset.squadMode===mode)));
  }
  squadModeButtons.forEach(b=>b.addEventListener('click',()=>showSquadMode(b.dataset.squadMode)));
  showSquadMode('list');

  const tacticsData=squadPanel.querySelector('#desk-tactics-data');
  if(tacticsData&&squadTacticsPane){
    let initial=null;
    try{initial=JSON.parse(tacticsData.textContent);}catch(_){}
    if(initial&&Array.isArray(initial.players)){
      const players=new Map(initial.players.map(p=>[Number(p.player_id),p]));
      const slots=initial.formations||{};
      const benchLimit=Number(initial.bench_limit)||7;
      let formation=initial.formation;
      let xi=initial.xi.map(p=>({player_id:Number(p.player_id),x:Number(p.x),y:Number(p.y)}));
      let bench=initial.bench.map(Number);
      let reserves=initial.reserves.map(Number);
      let selected=null;
      let isSaving=false;
      const pitch=squadTacticsPane.querySelector('[data-tactics-pitch]');
      const pitchLayer=squadTacticsPane.querySelector('[data-pitch-players]');
      const benchList=squadTacticsPane.querySelector('[data-roster-list="bench"]');
      const reserveList=squadTacticsPane.querySelector('[data-roster-list="reserves"]');
      const formationSelect=squadTacticsPane.querySelector('[data-tactics-formation]');
      const status=squadTacticsPane.querySelector('[data-tactics-status]');
      const saveButton=squadTacticsPane.querySelector('[data-tactics-save]');
      const resetButton=squadTacticsPane.querySelector('[data-tactics-reset]');
      const clamp=(v,minimum,maximum)=>Math.min(maximum,Math.max(minimum,v));
      function where(id){
        const j=xi.findIndex(e=>e.player_id===id);
        if(j>=0)return {group:'xi',index:j,entry:xi[j]};
        const k=bench.indexOf(id);
        if(k>=0)return {group:'bench',index:k};
        const m=reserves.indexOf(id);
        return m>=0?{group:'reserves',index:m}:null;
      }
      function point(event){
        const rect=pitch.getBoundingClientRect();
        return {x:clamp((event.clientX-rect.left)*100/rect.width,7,93),
                y:clamp((event.clientY-rect.top)*100/rect.height,8,94)};
      }
      function note(text,error){
        status.textContent=text;
        status.style.color=error?'#ffb6aa':'#aee0ce';
      }
      function dirty(){note('Unsaved changes',false);}
      function nameOf(id){return players.get(id)?.name||'Player';}
      function nearest(x,y){
        let closest=0,distance=Infinity;
        xi.forEach((e,i)=>{
          const d=(e.x-x)**2+(e.y-y)**2;
          if(d<distance){distance=d;closest=i;}
        });
        return closest;
      }
      function move(id,to,x,y,swapId){
        const origin=where(id);
        if(!origin||!['xi','bench','reserves'].includes(to))return;
        if(to==='xi'&&origin.group==='xi'&&swapId===undefined){
          origin.entry.x=clamp(x??origin.entry.x,7,93);
          origin.entry.y=clamp(y??origin.entry.y,8,94);
          dirty();draw();return;
        }
        if(to===origin.group&&swapId===undefined)return;
        const former=origin.group==='xi'?{...origin.entry}:null;
        if(origin.group==='xi')xi.splice(origin.index,1);
        else if(origin.group==='bench')bench.splice(origin.index,1);
        else reserves.splice(origin.index,1);
        if(to==='xi'){
          const position={x:clamp(Number(x??50),7,93),y:clamp(Number(y??50),8,94)};
          let index=xi.findIndex(e=>e.player_id===swapId);
          if(index<0&&xi.length>=11)index=nearest(position.x,position.y);
          if(index>=0){
            const displaced=xi.splice(index,1)[0];
            position.x=displaced.x;position.y=displaced.y;
            if(origin.group==='bench')bench.splice(origin.index,0,displaced.player_id);
            else if(origin.group==='reserves')reserves.splice(origin.index,0,displaced.player_id);
            else xi.push({player_id:displaced.player_id,x:former.x,y:former.y});
          }
          xi.push({player_id:id,x:position.x,y:position.y});
        }else if(to==='bench'){
          if(bench.length>=benchLimit){
            const displaced=bench.shift();
            if(origin.group==='xi')xi.push({...former,player_id:displaced});
            else if(origin.group==='reserves')reserves.splice(origin.index,0,displaced);
            else bench.push(displaced);
          }else if(origin.group==='xi'){
            // Keep a full starting XI while moving a player to the bench.
            const replacement=reserves.length?reserves.shift():null;
            if(replacement!==null)xi.push({...former,player_id:replacement});
          }
          bench.push(id);
        }else{
          if(origin.group==='xi'){
            const replacement=bench.length?bench.shift():reserves.length?reserves.shift():null;
            if(replacement!==null)xi.push({...former,player_id:replacement});
          }
          reserves.push(id);
        }
        selected=null;dirty();draw();
      }
      function select(id){
        if(selected===id){selected=null;draw();return;}
        if(selected!==null&&where(id)&&where(selected)){
          const a=where(selected),b=where(id);
          if(a.group==='xi'){
            move(id,'xi',a.entry.x,a.entry.y,selected);
          }else if(b.group==='xi'){
            move(selected,'xi',b.entry.x,b.entry.y,id);
          }else{
            // Switch a bench player with a reserve without losing anyone.
            const old=a.group==='bench'?bench:reserves;
            const other=b.group==='bench'?bench:reserves;
            if(a.group!==b.group){
              old[a.index]=id;other[b.index]=selected;
              selected=null;dirty();draw();
            }else{selected=id;draw();}
          }
          return;
        }
        selected=id;note('Selected '+nameOf(id)+' — choose a destination',false);draw();
      }
      function makeChip(id,group){
        const player=players.get(id);
        const row=document.createElement('div');
        row.className='desk-tactics-player';
        row.draggable=true;row.tabIndex=0;row.setAttribute('role','button');
        row.setAttribute('aria-label','Select '+nameOf(id));
        row.dataset.playerId=String(id);row.dataset.selected=String(selected===id);
        const pos=document.createElement('span');pos.className='desk-tactics-pos';
        pos.textContent=player?.position||'—';
        const name=document.createElement('strong');name.textContent=nameOf(id);
        name.title=nameOf(id);
        const rating=document.createElement('span');rating.className='desk-tactics-ovr';
        rating.textContent=String(player?.overall||'—');
        const action=document.createElement('select');
        action.setAttribute('aria-label','Move '+nameOf(id)+' to');
        for(const [value,label] of [['','Move to…'],['xi','Starting XI'],
                                    ['bench','Subs'],['reserves','Reserves']]){
          const option=document.createElement('option');
          option.value=value;option.textContent=label;action.appendChild(option);
        }
        action.addEventListener('change',e=>{
          const destination=e.target.value;
          if(destination==='xi'){
            const coords=slots[formation]?.[xi.length]||{x:50,y:50};
            const x=Array.isArray(coords)?coords[0]:50;
            const y=Array.isArray(coords)?coords[1]:50;
            move(id,'xi',x,y);
          }else if(destination)move(id,destination);
        });
        row.addEventListener('click',e=>{if(e.target.closest('select'))return;select(id);});
        row.addEventListener('keydown',e=>{
          if(e.target!==row)return;
          if(e.key==='Enter'||e.key===' '){e.preventDefault();select(id);}
        });
        row.addEventListener('dragstart',e=>{
          e.dataTransfer.setData('text/plain',String(id));
          e.dataTransfer.effectAllowed='move';
          selected=id;
        });
        row.append(pos,name,rating,action);
        return row;
      }
      function makePitchPlayer(entry){
        const id=entry.player_id,p=players.get(id);
        const token=document.createElement('button');
        token.type='button';token.className='desk-pitch-token';
        token.style.left=entry.x+'%';token.style.top=entry.y+'%';
        token.draggable=true;token.dataset.selected=String(selected===id);
        token.dataset.playerId=String(id);
        token.setAttribute('aria-label',nameOf(id)+' '+(p?.position||'')+
          ', click to select or drag to change position');
        const disc=document.createElement('span');disc.className='desk-player-disc';
        disc.textContent=String(p?.overall||'—');
        const name=document.createElement('span');name.className='desk-player-name';
        name.textContent=nameOf(id);
        const pos=document.createElement('span');pos.className='desk-player-position';
        pos.textContent=p?.position||'';
        token.append(disc,name,pos);
        let drag=null;
        token.addEventListener('pointerdown',e=>{
          if(e.pointerType==='mouse'&&e.button!==0)return;
          drag={id:e.pointerId,startX:e.clientX,startY:e.clientY,
                moved:false};
          try{token.setPointerCapture(e.pointerId);}catch(_){}
        });
        token.addEventListener('pointermove',e=>{
          if(!drag||drag.id!==e.pointerId)return;
          if(Math.hypot(e.clientX-drag.startX,e.clientY-drag.startY)>7){
            drag.moved=true;
            const p=point(e);
            token.style.left=p.x+'%';token.style.top=p.y+'%';
          }
        });
        token.addEventListener('pointerup',e=>{
          if(!drag||drag.id!==e.pointerId)return;
          if(drag.moved){
            const p=point(e);drag=null;
            move(id,'xi',p.x,p.y);return;
          }
          drag=null;
        });
        token.addEventListener('dragstart',e=>{
          e.dataTransfer.setData('text/plain',String(id));
          e.dataTransfer.effectAllowed='move';selected=id;
        });
        token.addEventListener('click',e=>{
          e.stopPropagation();
          if(drag?.moved)return;
          select(id);
        });
        return token;
      }
      function draw(){
        pitchLayer.replaceChildren();
        xi.forEach(entry=>pitchLayer.appendChild(makePitchPlayer(entry)));
        benchList.replaceChildren(...bench.map(id=>makeChip(id,'bench')));
        reserveList.replaceChildren(...reserves.map(id=>makeChip(id,'reserves')));
        squadTacticsPane.querySelector('[data-xi-count]').textContent=String(xi.length);
        squadTacticsPane.querySelector('[data-bench-count]').textContent=bench.length+'/'+benchLimit;
        squadTacticsPane.querySelector('[data-reserve-count]').textContent=String(reserves.length);
      }
      function attachDrop(target,group){
        target.addEventListener('dragover',e=>{e.preventDefault();e.dataTransfer.dropEffect='move';});
        target.addEventListener('drop',e=>{
          e.preventDefault();
          const id=Number(e.dataTransfer.getData('text/plain'));
          if(!players.has(id))return;
          if(group==='xi'){
            const p=point(e);move(id,'xi',p.x,p.y);
          }else move(id,group);
        });
      }
      attachDrop(pitch,'xi');
      for(const group of ['bench','reserves']){
        const section=squadTacticsPane.querySelector('[data-roster-group="'+group+'"]');
        attachDrop(section,group);
        const button=document.createElement('button');
        button.type='button';button.className='desk-drop-action';
        button.textContent='Move selected here';
        button.addEventListener('click',()=>{
          if(selected!==null)move(selected,group);
          else note('Select a player first',true);
        });
        section.appendChild(button);
      }
      pitch.addEventListener('click',e=>{
        if(e.target.closest('.desk-pitch-token'))return;
        if(selected!==null){const p=point(e);move(selected,'xi',p.x,p.y);}
      });
      formationSelect.addEventListener('change',()=>{
        formation=formationSelect.value;
        const target=slots[formation]||[];
        xi=xi.map((entry,i)=>({
          player_id:entry.player_id,
          x:target[i]?.[0]??entry.x,
          y:target[i]?.[1]??entry.y
        }));
        dirty();draw();
      });
      resetButton.addEventListener('click',()=>{
        if(!window.confirm('Reset all player positions to this formation?'))return;
        const target=slots[formation]||[];
        xi=xi.map((entry,i)=>({
          player_id:entry.player_id,
          x:target[i]?.[0]??entry.x,
          y:target[i]?.[1]??entry.y
        }));
        dirty();draw();
      });
      saveButton.addEventListener('click',async ()=>{
        if(isSaving)return;
        if(xi.length!==11){
          note('Select exactly 11 starting players before saving',true);return;
        }
        if(bench.length>benchLimit){
          note('Too many players on the bench',true);return;
        }
        isSaving=true;saveButton.disabled=true;note('Saving tactics…',false);
        try{
          const form=new FormData();
          const csrf=squadPanel.querySelector('input[name="csrf"]')?.value;
          if(!csrf)throw new Error('Session expired; reload the Career Desk');
          form.set('csrf',csrf);
          form.set('layout',JSON.stringify({formation,xi,bench,reserves}));
          const response=await fetch(location.pathname+'/tactics/save',{
            method:'POST',body:form,credentials:'same-origin',
            headers:{Accept:'application/json'},cache:'no-store'
          });
          const result=await response.json().catch(()=>null);
          if(!response.ok||!result?.ok)
            throw new Error(result?.error||'Unable to save tactics');
          note('Tactics saved to this career',false);
        }catch(error){note(String(error.message||error),true);}
        finally{isSaving=false;saveButton.disabled=false;}
      });
      draw();
    }
  }

  // Sidebar, mobile bar, overview buttons and legacy #section links use
  // the same one-page view switcher; no cross-page navigation is required.
  function switchView(name,changeUrl){
    if(!views[name])name='dashboard';
    names.forEach(function(other){views[other].hidden=other!==name;});
    document.querySelectorAll('[data-desk-tab]').forEach(function(link){
      const active=link.dataset.deskTab===name;
      if(active)link.setAttribute('aria-current','page');
      else link.removeAttribute('aria-current');
    });
    const label=document.getElementById('desk-current-view');
    if(label)label.textContent=titles[name];
    if(changeUrl&&location.hash!=='#'+name){
      history.pushState(null,'','#'+name);
    }
    if(name==='inbox'){
      document.getElementById('desk-offer-toast')?.remove();
      markInboxViewed();
    }
    window.scrollTo({top:0,behavior:'auto'});
  }
  document.addEventListener('click',function(e){
    const nav=e.target.closest('[data-desk-tab]');
    if(nav){
      e.preventDefault();switchView(nav.dataset.deskTab,true);return;
    }
    const link=e.target.closest('a[href^="#"]');
    if(link){
      const target=link.getAttribute('href').slice(1);
      const resolved=views[target]?target:redirects[target];
      if(resolved){
        e.preventDefault();switchView(resolved,true);
      }
    }
  });
  window.addEventListener('hashchange',function(){switchView(viewForHash(),false);});
  window.addEventListener('popstate',function(){switchView(viewForHash(),false);});
  switchView(viewForHash(),false);

  // A second compact clock lives in the always-visible header. The existing
  // dashboard clock and per-club countdowns continue working unchanged.
  // If the authoritative deadline rolls over while the manager is still on
  // another tab, send the browser to the final transfer report. The server
  // performs registration, not the browser; this only selects the view.
  if(state==='open'){
    const deadline=Date.parse((document.getElementById('desk-header-clock')||{}).dataset?.deadline||'');
    if(Number.isFinite(deadline)){
      let moved=false;
      const deadlineWatcher=setInterval(function(){
        if(!moved&&Date.now()>=deadline){
          moved=true;
          clearInterval(deadlineWatcher);
          location.replace(location.pathname+'#transfers');
          location.reload();
        }
      },1000);
    }
  }
  const clock=document.getElementById('desk-header-clock');
  if(clock){
    const deadline=Date.parse(clock.dataset.deadline||'');
    function tick(){
      if(!Number.isFinite(deadline)||state==='not_started'){
        clock.textContent='Not started';return;
      }
      if(state==='closed'){clock.textContent='Closed';return;}
      const diff=Math.max(0,Math.ceil((deadline-Date.now())/1000));
      clock.textContent=String(Math.floor(diff/60)).padStart(2,'0')+':'+
        String(diff%60).padStart(2,'0');
    }
    tick();setInterval(tick,1000);
  }
})();
"""
