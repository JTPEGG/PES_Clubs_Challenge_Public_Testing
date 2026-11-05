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
.desk-inbox-tools{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:10px 0 20px}
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
      else if(id==='recruitment'||id==='scouting')destination='scouting';
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

  // Extract the shortlist already rendered in the recruitment card, rather
  // than introducing a second authoritative list or changing saved records.
  const shortlistHeading=views.scouting.querySelector('#shortlist');
  if(shortlistHeading&&shortlistHeading.parentElement){
    const wrapper=document.createElement('div');
    wrapper.className='card';
    const sectionHead=document.createElement('h2');
    sectionHead.textContent='Players you are tracking';
    views.shortlist.appendChild(sectionHead);
    views.shortlist.appendChild(wrapper);
    let node=shortlistHeading;
    while(node){
      const next=node.nextElementSibling;
      wrapper.appendChild(node);
      node=next;
    }
  }
  const shortlistTitle=views.shortlist.querySelector('h3#shortlist');
  if(shortlistTitle)shortlistTitle.hidden=true;
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
      const sub=document.createElement('p');sub.className='muted';
      sub.textContent=entry.suffix+' · '+gbp(entry.total)+' modelled allocation';
      const track=document.createElement('div');track.className='desk-finance-track';
      const fill=document.createElement('div');fill.className='desk-finance-fill';
      fill.style.width=Math.min(100,Math.max(0,entry.remaining/Math.max(1,entry.total)*100))+'%';
      track.appendChild(fill);
      card.appendChild(label);card.appendChild(val);card.appendChild(track);card.appendChild(sub);
      grid.appendChild(card);
    });
    views.finances.appendChild(grid);
    const caption=document.createElement('p');caption.className='muted';
    caption.textContent='Figures include funds reserved for active negotiations and signed deals. Proposals are only indicative until agreed.';
    views.finances.appendChild(caption);
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

  // One place for all offers concerning the same player. Forms and controls
  // stay attached to their original offers.
  const inboxGrid=views.inbox.querySelector(':scope > .grid');
  const offerCards=inboxGrid?Array.from(inboxGrid.querySelectorAll(':scope > .offer[data-desk-player]')):[];
  if(inboxGrid&&offerCards.length){
    const seen=new Map();
    offerCards.forEach(function(card){
      const key=card.dataset.deskPlayer;
      if(!seen.has(key))seen.set(key,[]);
      seen.get(key).push(card);
    });
    seen.forEach(function(cards){
      if(cards.length<2)return;
      const holder=document.createElement('details');
      holder.className='desk-grouped-offer';holder.open=true;
      const sum=document.createElement('summary');
      const heading=document.createElement('span');
      heading.textContent=cards[0].dataset.deskPlayerName||'Player';
      const count=document.createElement('span');count.className='desk-group-count';
      count.textContent=cards.length+' competing bids';
      sum.appendChild(heading);sum.appendChild(count);
      const inner=document.createElement('div');inner.className='desk-grouped-grid';
      inboxGrid.insertBefore(holder,cards[0]);
      holder.appendChild(sum);holder.appendChild(inner);
      cards.forEach(function(card){inner.appendChild(card);});
    });
  }

  // Fast client-side inbox filters. Refreshing the market fetches genuine
  // updates from Flask, but switching views and narrowing visible cards
  // never needs a page request.
  if(offerCards.length){
    const toolbar=document.createElement('div');
    toolbar.className='desk-inbox-tools';
    let activeFilter='all';
    let playerQuery='';
    const filters=[
      ['all','All offers'],['action','Action needed'],
      ['talks','Negotiating'],['signed','Signed'],['closed','Rejected / closed']
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
      offerCards.forEach(function(card){card.hidden=!qualifies(card);});
      inboxGrid.querySelectorAll('.desk-grouped-offer').forEach(function(holder){
        const visible=Array.from(holder.querySelectorAll('.offer')).filter(function(card){
          return !card.hidden;
        });
        holder.hidden=visible.length===0;
        const counter=holder.querySelector('.desk-group-count');
        if(counter)counter.textContent=visible.length+' of '+
          holder.querySelectorAll('.offer').length+' bids shown';
      });
      let visible=offerCards.some(function(card){return !card.hidden;});
      const previous=views.inbox.querySelector('.desk-no-match');
      if(previous)previous.remove();
      if(!visible){
        const noMatch=emptyPanel('No offers match','Try a different player, club or status filter.');
        noMatch.classList.add('desk-no-match');
        toolbar.insertAdjacentElement('afterend',noMatch);
      }
    }
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
      filterCell.appendChild(filter);
      filterRow.appendChild(filterCell);
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
    table.tHead.appendChild(filterRow);
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
  // Server-backed infinite scrolling: no Next button, no 80-player cap,
  // no full Career Desk reload and no duplicate market tick on filter changes.
  const scoutForm=views.scouting.querySelector('form.scout-filters');
  const scoutTable=views.scouting.querySelector('table[data-scout-results]');
  const scoutProgress=views.scouting.querySelector('[data-scout-progress]');
  if(scoutForm&&scoutTable&&scoutProgress){
    const tableBody=scoutTable.tBodies[0];
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
          player.value,player.contract,player.years_left,player.pace,
          player.shooting,player.passing,player.dribbling,
          player.defending,player.physicality];
        if(scoutForm.elements.scout_attribute.value)
          fields.push(player.detail_attribute);
        fields.forEach(function(value){
          const cell=document.createElement('td');
          cell.textContent=display(value);
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
  const labels={
    proposed:'New offer',countered:'Awaiting buyer',
    accepted_pending_contract:'Player/agent talks',
    agreed_future:'Signed — registering at deadline',
    completed:'Registered for season',
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
        status==='agreed_future'?'Signed — registering at the deadline.':
        status==='rejected'?'Offer rejected.':
        status==='withdrawn'?'Negotiation withdrawn.':
        status==='completed'?'Transfer registered.':'';
    }
  }
  function updateOfferRow(offer){
    if(!outgoing)return;
    const row=outgoing.tBodies[0].querySelector(
      '[data-live-offer-id="'+Number(offer.offer_id)+'"]');
    if(row&&row.cells.length>3)
      row.cells[3].textContent=labels[offer.status]||offer.status;
  }
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
  window.fc27SyncIncomingOffers=function(items,csrf){
    if(!Array.isArray(items))return;
    for(const o of items.slice().reverse()){
      const id=Number(o.offer_id);
      if(!Number.isSafeInteger(id)||id<=0)continue;
      if(!seen.has(id)&&stream){
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
        stream.hidden=false;stream.prepend(card);
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
        row.cells[4].textContent=String(o.received_at||'').slice(11,16)+' UTC';
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
