"""Native SVG cursor and bounded, non-interactive click paw prints."""
from urllib.parse import quote

PAW = '<ellipse cx="10" cy="11" rx="4" ry="5" transform="rotate(-25 10 11)"/><ellipse cx="20" cy="7" rx="4" ry="5"/><ellipse cx="30" cy="11" rx="4" ry="5" transform="rotate(25 30 11)"/><ellipse cx="35" cy="20" rx="3.5" ry="4.5" transform="rotate(35 35 20)"/><path d="M10 28C10 23 15 17 20 17S30 23 30 28C30 34 24 32 20 31C16 32 10 34 10 28Z"/>'
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">'
CURSOR = SVG + '<defs><radialGradient id="j" cx="35%" cy="25%" r="80%"><stop stop-color="#ffdce9"/><stop offset=".55" stop-color="#f59cbb"/><stop offset="1" stop-color="#dc648f"/></radialGradient></defs><g fill="url(#j)" stroke="#b94c75" stroke-width="1.2">' + PAW + '</g><g fill="white" opacity=".7"><ellipse cx="17" cy="23" rx="3" ry="1.5"/><ellipse cx="19" cy="5" rx="1.5" ry="1"/></g></svg>'
PRINT = SVG + '<g fill="#17191b">' + PAW + '</g></svg>'


def cursor_html(reduced=False):
    import json
    import base64
    return '''<style>
@media (hover:hover) and (pointer:fine) {
 html,body,.stApp,.stApp * {cursor:url("data:image/svg+xml,''' + quote(CURSOR, safe='') + '''") 20 20,auto!important;}
 .stApp input,.stApp textarea,.stApp [contenteditable="true"] {cursor:text!important;}
}
.h-paw-print {position:fixed;width:34px;height:34px;pointer-events:none!important;z-index:2147483647;transform:translate(-50%,-50%) rotate(-12deg);}
.h-paw-print svg {display:block;width:100%;height:100%;}
</style><script>
(() => {
 const key='__hoduPawCursor';
 window[key]?.abort();
 document.querySelectorAll('.h-paw-print').forEach(el=>el.remove());
 const controller=new AbortController();window[key]=controller;
 const timers=new Set();
 controller.signal.addEventListener('abort',()=>{timers.forEach(clearTimeout);timers.clear();});
 const reduced=''' + json.dumps(bool(reduced)) + ''';
 document.addEventListener('pointerdown',event=>{
  if(event.pointerType!=='mouse'||event.button!==0) return;
  // Hodu's own petting art is the feedback; keep click stamps off its face.
  if(event.target.closest('.h-emotion')) return;
  const marks=document.querySelectorAll('.h-paw-print');
  if(marks.length>=20) marks[0].remove();
  const el=document.createElement('span');el.className='h-paw-print';
  el.setAttribute('aria-hidden','true');el.style.left=event.clientX+'px';el.style.top=event.clientY+'px';
  el.innerHTML=atob(''' + json.dumps(base64.b64encode(PRINT.encode()).decode()) + ''');
  document.body.appendChild(el);
  const quiet=reduced||matchMedia('(prefers-reduced-motion:reduce)').matches;
  if(!quiet) el.animate([{opacity:.78},{opacity:.65,offset:.2},{opacity:0}],{duration:2200,fill:'forwards'});
  const timer=setTimeout(()=>{el.remove();timers.delete(timer);},quiet?150:2250);timers.add(timer);
 },{capture:true,passive:true,signal:controller.signal});
})();
</script>'''
