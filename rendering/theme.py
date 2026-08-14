"""Shared rendering theme primitives.

PR1 keeps the existing visual output intact.  The CSS lives here so later
visual work can change one shared theme without coupling it to page data
formatting or the screenshot adapter.
"""

STYLE = """
<style>
*{box-sizing:border-box}html,body{width:100%;min-height:100%;margin:0;overflow:hidden;background:#0b1020;color:#f5f7ff;font-family:"Microsoft YaHei","Noto Sans SC",sans-serif}
.card{width:100vw;padding:42px;background:radial-gradient(circle at 90% 0,#263b72 0,transparent 32%),linear-gradient(145deg,#151d38,#090d19)}
.head{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:26px}.title{font-size:42px;font-weight:800}.sub{color:#aebbd9;font-size:20px;margin-top:8px}.badge{padding:9px 18px;border-radius:20px;background:#2e61ff;font-size:20px;font-weight:700}
.matches{display:grid;grid-template-columns:1fr 1fr;gap:14px}.match,.team{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:20px}.match{display:grid;grid-template-columns:54px 1fr auto;gap:16px;align-items:center}.index{font-size:28px;color:#8494bb}.main{font-size:23px;font-weight:700}.meta{font-size:17px;color:#aebbd9;margin-top:8px}.kda{font-size:24px;font-weight:800;text-align:right}.win{color:#70e1a1}.loss{color:#ff7188}.unknown{color:#b9c1d5}
.overview{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}.metric{background:rgba(255,255,255,.07);border-radius:15px;padding:16px}.metric b{display:block;font-size:21px;margin-top:5px}.metric span{color:#9eaccd;font-size:15px}.teams{display:grid;grid-template-columns:1fr 1fr;gap:16px}.team-title{font-size:25px;font-weight:800;margin-bottom:13px}.player{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr) auto;gap:10px;padding:12px 0;border-top:1px solid rgba(255,255,255,.09)}.player:first-of-type{border-top:0}.name{font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hero,.stats{color:#b7c2df}.extra{grid-column:1/-1;color:#8f9cbd;font-size:14px}.empty{padding:36px;text-align:center;color:#aebbd9;background:rgba(255,255,255,.06);border-radius:18px}
.hero-list{display:grid;grid-template-columns:1fr 1fr;gap:14px}.hero-row{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:18px}.hero-row .main{margin-bottom:8px}
</style>
"""
