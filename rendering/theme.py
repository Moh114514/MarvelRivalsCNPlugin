"""Shared Marvel Rivals visual tokens and CSS primitives."""

STYLE = """
<style>
:root{
  --mr-ink:#07111f;
  --mr-night:#0b1728;
  --mr-panel:#102236;
  --mr-panel-strong:#162b42;
  --mr-panel-soft:rgba(19,43,65,.72);
  --mr-yellow:#f4c542;
  --mr-yellow-hot:#ffe48a;
  --mr-cyan:#42dce3;
  --mr-red:#d57982;
  --mr-text:#f5f7ff;
  --mr-muted:#91a7bd;
  --mr-muted-strong:#b9c9d8;
  --mr-line:rgba(143,190,215,.2);
  --mr-line-soft:rgba(143,190,215,.1);
  --mr-shadow:0 18px 48px rgba(0,0,0,.28);
  --mr-radius:2px;
}

*{box-sizing:border-box}
html,body{width:100%;min-height:100%;margin:0;overflow-x:hidden;background:var(--mr-ink);color:var(--mr-text);font-family:"Microsoft YaHei","Noto Sans SC",sans-serif}
body{font-size:16px}

.mr-page{position:relative;isolation:isolate;width:100vw;min-height:100vh;overflow:hidden;background:linear-gradient(145deg,var(--mr-night) 0%,var(--mr-ink) 72%);color:var(--mr-text)}
.mr-page__background{position:absolute;inset:0;z-index:-2;overflow:hidden;background:radial-gradient(circle at 100% 0,rgba(42,87,122,.48),transparent 30%),linear-gradient(145deg,var(--mr-night),var(--mr-ink))}
.mr-page__background:before{position:absolute;inset:0;content:"";opacity:.52;background-image:linear-gradient(rgba(112,186,207,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(112,186,207,.045) 1px,transparent 1px);background-size:32px 32px;mask-image:linear-gradient(120deg,rgba(0,0,0,.9),transparent 72%)}
.mr-page__background:after{position:absolute;top:-8%;right:-12%;width:58%;height:42%;content:"";transform:skewX(-24deg);background:linear-gradient(125deg,transparent 0 43%,rgba(66,220,227,.18) 43.2% 43.7%,transparent 44% 52%,rgba(244,197,66,.2) 52.2% 52.7%,transparent 53%);opacity:.7}
.mr-page__slash{position:absolute;top:0;left:0;z-index:-1;width:min(70vw,860px);height:170px;background:linear-gradient(118deg,var(--mr-yellow) 0 58%,var(--mr-yellow-hot) 58% 61%,transparent 61%);clip-path:polygon(0 0,100% 0,74% 100%,0 100%);opacity:.95}
.mr-page__slash:after{position:absolute;right:6%;bottom:22px;width:30%;height:3px;content:"";transform:skewX(-28deg);background:var(--mr-cyan);box-shadow:0 12px 0 rgba(66,220,227,.35)}
.mr-page[data-watermark]:before{position:absolute;right:-3vw;bottom:3vh;z-index:-1;content:attr(data-watermark);color:rgba(178,213,228,.045);font-size:clamp(72px,13vw,180px);font-weight:900;letter-spacing:.08em;line-height:.8;pointer-events:none;transform:rotate(-8deg);white-space:nowrap}

.mr-page__inner{position:relative;width:min(100% - 48px,1320px);margin:0 auto;padding:54px 0 24px}
.mr-header{position:relative;display:flex;justify-content:space-between;gap:32px;align-items:flex-end;margin-bottom:30px;padding:22px 0 24px;border-bottom:1px solid var(--mr-line)}
.mr-header:after{position:absolute;bottom:-2px;left:0;width:150px;height:3px;content:"";background:var(--mr-yellow)}
.mr-header__copy{min-width:0}
.mr-header__eyebrow{margin-bottom:10px;color:var(--mr-cyan);font-size:13px;font-weight:800;letter-spacing:.18em;text-transform:uppercase}
.mr-header__title{margin:0;color:var(--mr-text);font-size:clamp(34px,5vw,68px);font-weight:900;letter-spacing:.05em;line-height:.95;text-shadow:2px 2px 0 rgba(7,17,31,.65);text-transform:uppercase}
.mr-header__title-cn{margin-top:10px;color:var(--mr-yellow-hot);font-size:clamp(20px,2.5vw,30px);font-weight:800;letter-spacing:.04em}
.mr-header__meta{margin-top:14px;color:var(--mr-muted-strong);font-size:15px;line-height:1.6}
.mr-season{flex:0 0 auto;align-self:flex-start;min-width:112px;padding:10px 14px;border:1px solid var(--mr-yellow);border-left:5px solid var(--mr-yellow);border-radius:var(--mr-radius);background:rgba(244,197,66,.08);color:var(--mr-yellow-hot);font-size:15px;font-weight:900;letter-spacing:.08em;text-align:center;text-transform:uppercase}

.mr-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:0 0 30px}
.mr-metric{position:relative;min-height:98px;padding:16px 18px;border:1px solid var(--mr-line);border-left:3px solid var(--mr-cyan);border-radius:var(--mr-radius);background:linear-gradient(135deg,rgba(24,54,79,.86),rgba(10,27,44,.78));box-shadow:var(--mr-shadow);overflow:hidden}
.mr-metric:after{position:absolute;right:-24px;bottom:-34px;width:92px;height:74px;content:"";transform:rotate(-34deg);border-top:1px solid rgba(244,197,66,.45)}
.mr-metric__label{display:block;color:var(--mr-muted);font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.mr-metric__value{display:block;margin-top:9px;color:var(--mr-text);font-size:clamp(21px,2.4vw,32px);font-weight:900;line-height:1.05;overflow-wrap:anywhere}

.mr-section{margin-top:28px}
.mr-section-heading{display:flex;align-items:center;gap:12px;margin:0 0 14px}
.mr-section-heading__rule{width:28px;height:3px;background:var(--mr-yellow)}
.mr-section-heading__kicker{color:var(--mr-cyan);font-size:12px;font-weight:800;letter-spacing:.18em;text-transform:uppercase}
.mr-section-heading__title{margin:0;color:var(--mr-text);font-size:21px;font-weight:900;letter-spacing:.06em}

.mr-hero-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.mr-hero-row{position:relative;display:grid;gap:6px;padding:15px 18px;border:1px solid var(--mr-line);border-left:3px solid var(--mr-yellow);border-radius:var(--mr-radius);background:var(--mr-panel-soft);box-shadow:var(--mr-shadow);overflow:hidden}
.mr-hero-row:before{position:absolute;top:0;right:0;width:34%;height:100%;content:"";background:linear-gradient(120deg,transparent 0 48%,rgba(66,220,227,.08) 48.5% 49.5%,transparent 50%)}
.mr-hero-row__title,.mr-hero-row__meta{position:relative;z-index:1}
.mr-hero-row__title{color:var(--mr-text);font-size:19px;font-weight:900}
.mr-hero-row__meta{color:var(--mr-muted-strong);font-size:14px;line-height:1.45}

.mr-match-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.mr-match-row{position:relative;display:grid;grid-template-columns:64px minmax(0,1fr) auto;gap:14px;align-items:center;padding:15px 18px;border:1px solid var(--mr-line);border-left:3px solid var(--mr-cyan);border-radius:var(--mr-radius);background:var(--mr-panel-soft);box-shadow:var(--mr-shadow);overflow:hidden}
.mr-match-row:after{position:absolute;right:-22px;bottom:-34px;width:100px;height:70px;content:"";transform:rotate(-34deg);border-top:1px solid rgba(66,220,227,.32)}
.mr-match-row__index{position:relative;z-index:1;color:var(--mr-yellow);font-size:30px;font-weight:900;letter-spacing:.04em}
.mr-match-row__main,.mr-match-row__meta,.mr-match-row__kda{position:relative;z-index:1}
.mr-match-row__main{font-size:18px;font-weight:900;line-height:1.25}
.mr-match-row__result{margin-right:6px}
.mr-match-row__result--win{color:var(--mr-yellow-hot)}
.mr-match-row__result--loss{color:var(--mr-red)}
.mr-match-row__result--unknown{color:var(--mr-muted-strong)}
.mr-match-row__meta{margin-top:6px;color:var(--mr-muted);font-size:13px;line-height:1.45}
.mr-match-row__kda{color:var(--mr-text);font-size:20px;font-weight:900;white-space:nowrap}

.mr-team-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.mr-team{position:relative;border:1px solid var(--mr-line);border-top:3px solid var(--mr-muted);border-radius:var(--mr-radius);background:var(--mr-panel-soft);box-shadow:var(--mr-shadow);overflow:hidden}
.mr-team--winner{border-color:rgba(244,197,66,.5);border-top-color:var(--mr-yellow)}
.mr-team--loss{border-top-color:var(--mr-red)}
.mr-team__header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:16px 18px 12px;border-bottom:1px solid var(--mr-line-soft)}
.mr-team__name{color:var(--mr-text);font-size:22px;font-weight:900;letter-spacing:.08em}
.mr-team--winner .mr-team__name{color:var(--mr-yellow-hot)}
.mr-team__raw{margin-top:4px;color:var(--mr-muted);font-size:13px}
.mr-team__result{font-size:12px;font-weight:900;letter-spacing:.14em;text-align:right}
.mr-team--winner .mr-team__result{color:var(--mr-cyan)}
.mr-team--loss .mr-team__result{color:var(--mr-red)}
.mr-team--unknown .mr-team__result{color:var(--mr-muted)}
.mr-team__members{padding:0 18px}
.mr-player-row{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr) auto;gap:10px;padding:12px 0;border-top:1px solid var(--mr-line-soft)}
.mr-player-row:first-child{border-top:0}
.mr-player-row__name{min-width:0;color:var(--mr-text);font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mr-player-row__hero,.mr-player-row__stats{color:var(--mr-muted-strong);font-size:14px}
.mr-player-row__stats{font-weight:800;text-align:right;white-space:nowrap}
.mr-player-row__extra{grid-column:1/-1;color:var(--mr-muted);font-size:12px}

.mr-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:150px;padding:24px;border:1px dashed var(--mr-line);border-radius:var(--mr-radius);background:rgba(10,28,45,.64);color:var(--mr-muted-strong);text-align:center}
.mr-empty__mark{margin-bottom:8px;color:var(--mr-yellow);font-size:12px;font-weight:900;letter-spacing:.2em}
.mr-footer{display:flex;justify-content:space-between;gap:16px;margin-top:36px;padding-top:12px;border-top:1px solid var(--mr-line-soft);color:var(--mr-muted);font-size:11px;font-weight:800;letter-spacing:.16em;line-height:1.5;text-transform:uppercase}

@media (max-width:900px){
  .mr-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
  .mr-match-list{grid-template-columns:1fr}
}
@media (max-width:760px){
  .mr-page__inner{width:min(100% - 32px,1320px);padding-top:40px}
  .mr-page__slash{height:128px;width:92vw}
  .mr-header{gap:18px;margin-bottom:24px;padding-top:14px}
  .mr-header__title{font-size:clamp(29px,9vw,48px)}
  .mr-header__title-cn{font-size:21px}
  .mr-header__meta{font-size:13px}
  .mr-season{min-width:88px;padding:8px 9px;font-size:12px}
  .mr-hero-list,.mr-team-list{grid-template-columns:1fr}
}
@media (max-width:520px){
  .mr-metrics{gap:7px;margin-bottom:24px}
  .mr-metric{min-height:82px;padding:12px}
  .mr-metric__label{font-size:11px}
  .mr-metric__value{font-size:21px}
  .mr-match-row{grid-template-columns:48px minmax(0,1fr);gap:10px;padding:13px}
  .mr-match-row__index{font-size:25px}
  .mr-match-row__main{font-size:16px}
  .mr-match-row__kda{grid-column:2;font-size:17px;text-align:left}
  .mr-player-row{grid-template-columns:minmax(0,1fr) auto}
  .mr-player-row__hero{grid-column:1}
  .mr-player-row__stats{grid-column:2;grid-row:1 / span 2}
  .mr-footer{flex-direction:column;gap:4px}
}
</style>
"""
