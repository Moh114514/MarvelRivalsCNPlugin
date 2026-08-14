"""Shared Marvel Rivals low-noise visual tokens and CSS primitives."""

STYLE = """
<style>
:root{
  --mr-ink:#241c3d;
  --mr-night:#302452;
  --mr-indigo:#4e397f;
  --mr-purple:#6540ae;
  --mr-purple-deep:#2f205b;
  --mr-paper:#e9e6f0;
  --mr-paper-strong:#fffdf8;
  --mr-panel:var(--mr-paper);
  --mr-yellow:#ffd51f;
  --mr-yellow-hot:#fff06a;
  --mr-cyan:#58d9dc;
  --mr-red:#b9405c;
  --mr-text:#fffdf8;
  --mr-ink-text:#241c3d;
  --mr-muted:#756d88;
  --mr-muted-strong:#554b6d;
  --mr-line:#cbc4d8;
  --mr-line-soft:rgba(47,32,91,.16);
  --mr-line-dark:rgba(255,253,248,.24);
  --mr-shadow:none;
  --mr-radius:0;
}

*{box-sizing:border-box}
html,body{width:100%;min-height:100%;margin:0;overflow-x:hidden;background:var(--mr-paper);color:var(--mr-ink-text);font-family:"Microsoft YaHei","Noto Sans SC",sans-serif}
body{font-size:17px}

.mr-page{position:relative;isolation:isolate;width:100vw;min-height:100vh;overflow:hidden;background:var(--mr-paper);color:var(--mr-ink-text)}
.mr-page__background{position:absolute;inset:0;z-index:-2;overflow:hidden;background:var(--mr-paper)}
.mr-page__background:before{position:absolute;inset:0;content:"";opacity:.28;background:linear-gradient(135deg,transparent 0 31%,rgba(101,64,174,.09) 31.2% 43%,transparent 43.2% 67%,rgba(101,64,174,.06) 67.2% 81%,transparent 81.2%),linear-gradient(25deg,transparent 0 58%,rgba(255,255,255,.46) 58.2% 68%,transparent 68.2%)}
.mr-page__background:after{position:absolute;left:0;bottom:0;width:100%;height:34px;content:"";background:linear-gradient(175deg,transparent 0 38%,var(--mr-yellow) 38.2% 71%,transparent 71.2%);opacity:.92}
.mr-page__slash{position:absolute;top:0;left:0;z-index:-1;width:100%;height:78px;background:linear-gradient(175deg,var(--mr-yellow) 0 18px,transparent 18.2%);clip-path:polygon(0 0,100% 0,88% 100%,0 78%);opacity:.96}
.mr-page__slash:after{display:none}
.mr-page[data-watermark]:before{position:absolute;right:-3vw;bottom:3vh;z-index:-1;content:"";pointer-events:none}

.mr-page__inner{position:relative;width:min(calc(100% - 48px),1320px);margin:0 auto;padding:50px 0 28px}
.mr-header{position:relative;display:flex;justify-content:space-between;gap:32px;align-items:flex-start;margin-bottom:30px;padding:28px 0 24px;border-bottom:3px solid var(--mr-ink)}
.mr-header:after{position:absolute;bottom:-7px;left:0;width:156px;height:7px;content:"";background:var(--mr-yellow)}
.mr-header__copy{min-width:0}
.mr-header__eyebrow{margin-bottom:9px;color:var(--mr-muted);font-size:13px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.mr-header__title{margin:0;color:var(--mr-purple-deep);font-size:clamp(18px,2.8vw,29px);font-weight:950;letter-spacing:.11em;line-height:1;text-transform:uppercase}
.mr-header__nameplate{display:flex;align-items:center;width:fit-content;max-width:min(100%,760px);margin-top:14px;padding:7px 20px 9px 14px;border:3px solid var(--mr-yellow);background:var(--mr-purple-deep);box-shadow:5px 5px 0 var(--mr-yellow);clip-path:polygon(0 0,98% 0,100% 70%,96% 100%,0 100%)}
.mr-header__title-cn{color:var(--mr-paper-strong);font-size:clamp(28px,4.2vw,44px);font-weight:950;letter-spacing:.03em;line-height:1.05;overflow-wrap:anywhere}
.mr-header__meta{margin-top:17px;color:var(--mr-muted-strong);font-size:17px;font-weight:700;line-height:1.55}
.mr-header__meta-grid{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}
.mr-header__meta-item{min-width:120px;padding:8px 14px 10px;border-left:5px solid var(--mr-purple);background:var(--mr-paper-strong);color:var(--mr-ink-text)}
.mr-header__meta-item:first-child{border-left-color:var(--mr-yellow);background:var(--mr-purple-deep);color:var(--mr-text)}
.mr-header__meta-label{display:block;color:var(--mr-muted);font-size:13px;font-weight:850;letter-spacing:.04em}
.mr-header__meta-item:first-child .mr-header__meta-label{color:#d7cceb}
.mr-header__meta-value{display:block;margin-top:3px;color:var(--mr-purple-deep);font-size:19px;font-weight:950;line-height:1.15;overflow-wrap:anywhere}
.mr-header__meta-item:first-child .mr-header__meta-value{color:var(--mr-yellow)}
.mr-season{flex:0 0 auto;align-self:flex-start;min-width:128px;padding:12px 15px;border:3px solid var(--mr-purple-deep);background:var(--mr-yellow);box-shadow:4px 4px 0 var(--mr-purple-deep);color:var(--mr-purple-deep);font-size:16px;font-weight:950;letter-spacing:.06em;line-height:1.3;text-align:center;clip-path:polygon(0 0,100% 0,92% 100%,0 100%)}

.mr-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;margin:0 0 34px;border-top:3px solid var(--mr-purple-deep);border-bottom:3px solid var(--mr-purple-deep);background:var(--mr-paper-strong)}
.mr-metric{position:relative;min-height:112px;padding:17px 20px;border:0;border-right:2px solid var(--mr-line);background:transparent;color:var(--mr-ink-text);overflow:hidden}
.mr-metric:last-child{border-right:0}
.mr-metric:nth-child(1),.mr-metric:nth-child(3){border-top:5px solid var(--mr-yellow);padding-top:12px}
.mr-metric:after{display:none}
.mr-metric__label{display:block;color:var(--mr-muted);font-size:15px;font-weight:850;letter-spacing:.08em;text-transform:uppercase}
.mr-metric__value{display:block;margin-top:10px;color:var(--mr-purple-deep);font-size:clamp(26px,3vw,38px);font-weight:950;line-height:1.05;overflow-wrap:anywhere}

.mr-section{margin-top:32px}
.mr-section-heading{display:flex;align-items:center;gap:14px;margin:0 0 16px}
.mr-section-heading__rule{width:44px;height:6px;background:var(--mr-yellow);box-shadow:4px 4px 0 var(--mr-purple-deep);transform:skewX(-24deg)}
.mr-section-heading__kicker{color:var(--mr-purple);font-size:14px;font-weight:950;letter-spacing:.16em;text-transform:uppercase}
.mr-section-heading__title{margin:0;color:var(--mr-ink-text);font-size:26px;font-weight:950;letter-spacing:.03em}

.mr-hero-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.mr-hero-row{position:relative;display:grid;grid-template-columns:62px minmax(0,1fr);gap:14px;min-height:92px;padding:16px 18px;border:0;border-bottom:2px solid var(--mr-line);background:var(--mr-paper-strong);color:var(--mr-ink-text);overflow:hidden}
.mr-hero-row:first-child{border-top:5px solid var(--mr-yellow);padding-top:13px}
.mr-hero-row:before{display:none}
.mr-hero-row__index{color:var(--mr-purple);font-size:32px;font-weight:950;line-height:1}
.mr-hero-row__body{display:grid;gap:4px}
.mr-hero-row__title{color:var(--mr-ink-text);font-size:22px;font-weight:950;line-height:1.15}
.mr-hero-row__meta{color:var(--mr-muted-strong);font-size:16px;line-height:1.35}

.mr-match-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.mr-match-row{position:relative;display:grid;grid-template-columns:68px minmax(0,1fr) auto;gap:15px;align-items:center;min-height:100px;padding:16px 18px;border:0;border-left:6px solid var(--mr-purple);border-bottom:2px solid var(--mr-line);background:var(--mr-paper-strong);color:var(--mr-ink-text);overflow:hidden}
.mr-match-row:after{display:none}
.mr-match-row__index,.mr-match-row__main,.mr-match-row__meta,.mr-match-row__kda{position:relative;z-index:1}
.mr-match-row__index{color:var(--mr-purple);font-size:34px;font-weight:950;letter-spacing:.04em}
.mr-match-row__main{font-size:20px;font-weight:950;line-height:1.25}
.mr-match-row__result{margin-right:7px}
.mr-match-row__result--win{color:var(--mr-purple)}
.mr-match-row__result--loss{color:var(--mr-red)}
.mr-match-row__result--unknown{color:var(--mr-muted-strong)}
.mr-match-row__meta{margin-top:7px;color:var(--mr-muted-strong);font-size:15px;line-height:1.45}
.mr-match-row__kda{color:var(--mr-ink-text);font-size:22px;font-weight:950;white-space:nowrap}

.mr-team-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.mr-team{position:relative;border:0;border-top:6px solid var(--mr-purple);background:var(--mr-paper-strong);color:var(--mr-ink-text);overflow:hidden}
.mr-team--winner{border-top-color:var(--mr-yellow)}
.mr-team--loss{border-top-color:var(--mr-red)}
.mr-team__header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:18px 20px 14px;border-bottom:2px solid var(--mr-line-soft)}
.mr-team__name{color:var(--mr-ink-text);font-size:24px;font-weight:950;letter-spacing:.06em}
.mr-team--winner .mr-team__name{color:var(--mr-purple)}
.mr-team__raw{margin-top:5px;color:var(--mr-muted-strong);font-size:15px}
.mr-team__result{font-size:14px;font-weight:950;letter-spacing:.14em;text-align:right}
.mr-team--winner .mr-team__result{color:var(--mr-purple)}
.mr-team--loss .mr-team__result{color:var(--mr-red)}
.mr-team--unknown .mr-team__result{color:var(--mr-muted)}
.mr-team__members{padding:0 20px}
.mr-player-row{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr) auto;gap:10px;padding:14px 0;border-top:2px solid var(--mr-line-soft)}
.mr-player-row:first-child{border-top:0}
.mr-player-row__name{min-width:0;color:var(--mr-ink-text);font-size:17px;font-weight:850;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mr-player-row__hero,.mr-player-row__stats{color:var(--mr-muted-strong);font-size:16px}
.mr-player-row__stats{font-weight:850;text-align:right;white-space:nowrap}
.mr-player-row__extra{grid-column:1/-1;color:var(--mr-muted);font-size:14px}

.mr-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:170px;padding:28px;border:2px solid var(--mr-purple);background:var(--mr-paper-strong);color:var(--mr-muted-strong);text-align:center}
.mr-empty__mark{margin-bottom:10px;color:var(--mr-purple);font-size:14px;font-weight:950;letter-spacing:.18em}
.mr-footer{display:flex;justify-content:space-between;gap:16px;margin-top:40px;padding-top:15px;border-top:3px solid var(--mr-ink);color:var(--mr-purple);font-size:14px;font-weight:900;letter-spacing:.1em;line-height:1.5}

@media (max-width:900px){
  .mr-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
  .mr-metric:nth-child(2){border-right:0}
  .mr-metric:nth-child(-n+2){border-bottom:2px solid var(--mr-line)}
  .mr-match-list{grid-template-columns:1fr}
}
@media (max-width:760px){
  .mr-page__inner{width:min(calc(100% - 32px),1320px);padding-top:36px}
  .mr-page__slash{height:68px}
  .mr-header{gap:18px;margin-bottom:28px;padding-top:18px}
  .mr-header__title{font-size:clamp(18px,5vw,26px)}
  .mr-header__nameplate{padding-right:14px}
  .mr-header__title-cn{font-size:clamp(26px,7vw,36px)}
  .mr-header__meta{font-size:16px}
  .mr-header__meta-item{min-width:110px}
  .mr-season{min-width:104px;padding:10px 11px;font-size:15px}
  .mr-hero-list,.mr-team-list{grid-template-columns:1fr}
}
@media (max-width:520px){
  .mr-page__inner{width:min(calc(100% - 24px),1320px)}
  .mr-header{align-items:stretch;flex-direction:column;padding-top:14px}
  .mr-header__nameplate{max-width:calc(100% - 8px)}
  .mr-season{align-self:flex-start}
  .mr-metrics{margin-bottom:28px}
  .mr-metric{min-height:96px;padding:15px}
  .mr-metric:nth-child(1),.mr-metric:nth-child(3){padding-top:10px}
  .mr-metric__label{font-size:14px}
  .mr-metric__value{font-size:25px}
  .mr-hero-row{grid-template-columns:52px minmax(0,1fr);gap:10px;padding:15px}
  .mr-hero-row:first-child{padding-top:12px}
  .mr-hero-row__index{font-size:28px}
  .mr-hero-row__title{font-size:20px}
  .mr-hero-row__meta{font-size:15px}
  .mr-match-row{grid-template-columns:52px minmax(0,1fr);gap:10px;padding:14px}
  .mr-match-row__index{font-size:29px}
  .mr-match-row__main{font-size:18px}
  .mr-match-row__kda{grid-column:2;font-size:20px;text-align:left}
  .mr-player-row{grid-template-columns:minmax(0,1fr) auto}
  .mr-player-row__hero{grid-column:1}
  .mr-player-row__stats{grid-column:2;grid-row:1 / span 2}
  .mr-footer{flex-direction:column;gap:5px;font-size:13px}
}
</style>
"""
