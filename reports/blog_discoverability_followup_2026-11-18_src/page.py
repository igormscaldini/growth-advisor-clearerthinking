"""Page shell for the report: tokens (light + dark), layout, and the one hover script the charts share."""

CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--border:rgba(11,11,11,.10);--series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;--series-4:#eda100;
--good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;--link:#1c5cab;--wash:#f0efec}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;
--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--series-1:#3987e5;--series-2:#d95926;
--series-3:#199e70;--series-4:#c98500;--link:#86b6ef;--wash:#262624}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:920px;margin:0 auto;padding:40px 20px 80px}
h1{font-size:30px;line-height:1.2;margin:0 0 6px;text-wrap:balance}
.sub{color:var(--ink2);font-size:14px;margin:0 0 28px}
h2{font-size:22px;margin:52px 0 10px;padding-top:26px;border-top:1px solid var(--grid);text-wrap:balance}
h3{font-size:17px;margin:30px 0 6px}
p{margin:10px 0}
a{color:var(--link)}
code{font:13px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--wash);padding:1px 5px;border-radius:4px;overflow-wrap:anywhere}
.verdict{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 22px;font-size:17px}
.verdict p:first-child{margin-top:0}.verdict p:last-child{margin-bottom:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:18px 0 6px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 18px}
.tile .label{font-size:13px;color:var(--ink2)}
.tile .value{font-size:30px;font-weight:600;line-height:1.15;margin:4px 0 2px}
.tile .value small{font-size:15px;font-weight:500;color:var(--ink2)}
.tile .note{font-size:13px;color:var(--ink2)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin:16px 0}
.card h3{margin:0 0 2px}.card .cap{font-size:13.5px;color:var(--ink2);margin:0 0 14px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14.5px}
th{text-align:left;font-weight:600;font-size:13px;color:var(--ink2);padding:8px 10px;border-bottom:1px solid var(--axis);vertical-align:bottom}
td{padding:10px;border-bottom:1px solid var(--grid);vertical-align:top}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.score td:first-child{font-weight:600;min-width:170px}
.chip{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;font-size:13px;font-weight:600;padding:3px 10px 3px 8px;border-radius:999px;background:var(--wash);color:var(--ink)}
.chip i{width:9px;height:9px;border-radius:50%;display:inline-block}
.chip.good i{background:var(--good)}.chip.around i{background:var(--series-1)}.chip.same i{background:var(--muted)}.chip.open i{background:var(--serious)}
.segbar{display:flex;gap:2px;height:28px}
.seg{border-radius:4px;font-size:13px;font-weight:600;line-height:28px;padding-left:8px;white-space:nowrap;min-width:3px;cursor:default}
.seg:hover,.seg:focus{filter:brightness(1.08);outline:none}
.legend{display:flex;flex-wrap:wrap;gap:6px 20px;margin-top:12px;font-size:13.5px;color:var(--ink2)}
.key i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.key b{color:var(--ink);font-weight:600}.key em{font-style:normal;color:var(--muted)}
svg.line{width:100%;min-width:560px;height:auto;display:block;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1}.axis{stroke:var(--axis);stroke-width:1}
.tick{fill:var(--muted);font-size:11.5px;font-variant-numeric:tabular-nums}
.series{fill:none;stroke:var(--series-1);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.dot,.hoverdot{fill:var(--series-1);stroke:var(--surface);stroke-width:2}
.endlabel{fill:var(--ink);font-size:13px;font-weight:600}
.event{stroke:var(--axis);stroke-width:1}.evlabel{fill:var(--ink2);font-size:11.5px}
.cross{stroke:var(--muted);stroke-width:1}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--surface);font-size:12.5px;padding:6px 9px;border-radius:6px;display:none;z-index:9;white-space:nowrap}
#tip b{font-size:14px;display:block}
details{margin:12px 0}summary{cursor:pointer;color:var(--ink2);font-size:14px}
details.tableview table{margin-top:8px;font-size:13px}details.tableview td,details.tableview th{padding:5px 10px}
ul{padding-left:22px}li{margin:6px 0}
.small{font-size:13.5px;color:var(--ink2)}
.urls{font-size:13px;columns:2;column-gap:28px;padding-left:18px}.urls li{margin:3px 0;overflow-wrap:anywhere;break-inside:avoid}
@media (max-width:640px){.urls{columns:1}h1{font-size:25px}.tile .value{font-size:26px}}
"""

JS = """
(function(){
  var tip=document.getElementById('tip');
  function show(e,head,sub){tip.textContent='';var b=document.createElement('b');b.textContent=head;tip.appendChild(b);
    tip.appendChild(document.createTextNode(sub));tip.style.display='block';
    var x=Math.min(e.clientX+14,window.innerWidth-tip.offsetWidth-8);tip.style.left=x+'px';tip.style.top=(e.clientY-tip.offsetHeight-12)+'px';}
  function hide(){tip.style.display='none';}
  document.querySelectorAll('.seg').forEach(function(s){
    var t=s.getAttribute('data-tip').split('|');
    s.addEventListener('pointermove',function(e){show(e,t[1],t[0]);});s.addEventListener('pointerleave',hide);
    s.addEventListener('focus',function(){var r=s.getBoundingClientRect();show({clientX:r.left,clientY:r.top},t[1],t[0]);});s.addEventListener('blur',hide);});
  document.querySelectorAll('svg.line').forEach(function(svg){
    var pts=svg.getAttribute('data-points').split(';').map(function(p){p=p.split(',');return {w:p[0],v:+p[1],x:+p[2],y:+p[3]};});
    var unit=svg.getAttribute('data-unit'),cross=svg.querySelector('.cross'),dot=svg.querySelector('.hoverdot'),hit=svg.querySelector('.hit');
    hit.addEventListener('pointermove',function(e){
      var box=svg.getBoundingClientRect(),vb=svg.viewBox.baseVal,x=(e.clientX-box.left)*vb.width/box.width,best=pts[0];
      pts.forEach(function(p){if(Math.abs(p.x-x)<Math.abs(best.x-x))best=p;});
      cross.setAttribute('x1',best.x);cross.setAttribute('x2',best.x);cross.setAttribute('visibility','visible');
      dot.setAttribute('cx',best.x);dot.setAttribute('cy',best.y);dot.setAttribute('visibility','visible');
      show(e,best.v.toLocaleString('en-US'),unit+', week of '+best.w);});
    hit.addEventListener('pointerleave',function(){cross.setAttribute('visibility','hidden');dot.setAttribute('visibility','hidden');hide();});});
})();
"""


def render(title: str, subtitle: str, body: str) -> str:
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><style>{CSS}</style></head><body><main>"
            f"<h1>{title}</h1><p class='sub'>{subtitle}</p>{body}</main><div id='tip'></div><script>{JS}</script></body></html>")
