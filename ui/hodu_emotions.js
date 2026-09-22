(() => {
  const config = __CONFIG__;
  window.__hoduEmotions?.abort();
  const controller = new AbortController();
  window.__hoduEmotions = controller;
  const {signal} = controller;
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  let button, timer, frame, point, near = false, hover = false, focused = false;
  const quiet = () => config.reduced || media.matches;
  const resting = () => hover || focused ? 'happy' : near ? 'curious' : 'idle';
  function render(state) {
    if (!button) return;
    button.dataset.emotion = state;
    button.dataset.reduced = String(quiet());
    const selected = quiet() ? null : button.querySelector(`[data-emotion-frame="${state}"]`);
    button.querySelector('.h-emotion-default').hidden = !!selected;
    button.querySelectorAll('[data-emotion-frame]').forEach(el => { el.hidden = el !== selected; });
  }
  function reset() {
    clearTimeout(timer); timer = null;
    near = hover = focused = false;
    if (button) {
      button.style.removeProperty('--look-x'); button.style.removeProperty('--look-angle');
      render('idle');
    }
  }
  function refresh() {
    if (!timer) render(resting());
  }
  function bind() {
    const next = document.querySelector('.h-emotion');
    if (next === button) return;
    reset(); button = next;
    if (!button) return;
    render('idle');
    button.addEventListener('pointerenter', e => { if(e.pointerType === 'mouse') {hover = true; refresh();} }, {signal});
    button.addEventListener('pointerleave', () => {hover = false; refresh();}, {signal});
    button.addEventListener('focus', () => {focused = true; refresh();}, {signal});
    button.addEventListener('blur', () => {focused = false; refresh();}, {signal});
    button.addEventListener('click', () => {
      if (timer) return;
      render('love');
      timer = setTimeout(() => {timer = null; refresh();}, config.states.love.durationMs);
    }, {signal});
  }
  document.addEventListener('pointermove', e => {
    if (e.pointerType !== 'mouse' || !button || quiet()) return;
    point = {x:e.clientX, y:e.clientY};
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      if (!button?.isConnected) return;
      const r = button.getBoundingClientRect();
      const dx = point.x - (r.left + r.width / 2), dy = point.y - (r.top + r.height / 2);
      near = Math.hypot(dx, dy) < Math.max(r.width, r.height) / 2 + 150;
      const amount = near ? Math.max(-1, Math.min(1, dx / 180)) : 0;
      button.style.setProperty('--look-x', `${amount * 7}px`);
      button.style.setProperty('--look-angle', `${amount * 3}deg`);
      refresh();
    });
  }, {passive:true, signal});
  document.documentElement.addEventListener('pointerleave', reset, {signal});
  window.addEventListener('blur', reset, {signal});
  document.addEventListener('visibilitychange', () => {if(document.hidden) reset();}, {signal});
  document.addEventListener('scroll', reset, {capture:true, passive:true, signal});
  media.addEventListener('change', reset, {signal});
  const observer = new MutationObserver(bind);
  observer.observe(document.body, {childList:true, subtree:true});
  signal.addEventListener('abort', () => {reset(); cancelAnimationFrame(frame); observer.disconnect();});
  bind();
})();
