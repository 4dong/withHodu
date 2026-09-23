(() => {
  const config = __CONFIG__;
  window.__hoduEmotions?.abort();
  const controller = new AbortController();
  window.__hoduEmotions = controller;
  const {signal} = controller;
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  let button, timer, autoTimer, frame, point, near = false, hover = false, focused = false;
  const quiet = () => config.reduced || media.matches;
  const reactions = {head: ['love', '쓰다듬어 주니 좋아해요 ♥'], belly: ['tickle', '간지러워요 ♪'], tail: ['shake', '호두가 부르르 털어요!']};
  const resting = () => hover || focused ? 'happy' : near ? 'curious' : 'idle';
  function render(state) {
    if (!button) return;
    button.dataset.emotion = state;
    button.style.setProperty('--emotion-duration', `${config.states[state].durationMs || 0}ms`);
    button.dataset.reduced = String(quiet());
    const reaction = Object.values(reactions).find(([emotion]) => emotion === state);
    const caption = button.querySelector('.h-emotion-caption');
    const message = reaction?.[1] || '머리·배·꼬리를 톡 눌러 보세요';
    if (caption.textContent !== message) caption.textContent = message;
    const selected = quiet() ? null : button.querySelector(`[data-emotion-frame="${state}"]`);
    button.querySelector('.h-emotion-default').hidden = !!selected;
    button.querySelectorAll('[data-emotion-frame]').forEach(el => { el.hidden = el !== selected; });
  }
  function reset() {
    clearTimeout(timer); timer = null;
    clearTimeout(autoTimer); autoTimer = null;
    cancelAnimationFrame(frame); frame = null;
    near = hover = focused = false;
    if (button) {
      button.style.removeProperty('--look-x'); button.style.removeProperty('--look-angle');
      render('idle');
    }
    scheduleIdle();
  }
  function refresh() {
    if (!timer) render(resting());
  }
  function scheduleIdle() {
    clearTimeout(autoTimer);
    if (signal.aborted || quiet() || document.hidden || !button?.isConnected) return;
    autoTimer = setTimeout(() => {
      if (!timer && !hover && !focused && !near) play('shake');
      else scheduleIdle();
    }, config.restMs);
  }
  function play(state) {
    clearTimeout(timer);
    clearTimeout(autoTimer);
    // Hiding the old sheet resets its frame clock. Every action starts at neutral.
    render('idle');
    void button.offsetWidth;
    render(state);
    timer = setTimeout(() => {
      timer = null;
      render(resting());
      scheduleIdle();
    }, config.states[state].durationMs);
  }
  function bind() {
    const next = document.querySelector('.h-emotion');
    if (next === button) return;
    reset(); button = next;
    if (!button) return;
    render('idle');
    scheduleIdle();
    button.addEventListener('pointerenter', e => { if(e.pointerType === 'mouse') {hover = true; refresh();} }, {signal});
    button.addEventListener('pointerleave', () => {hover = false; refresh();}, {signal});
    button.addEventListener('focusin', () => {focused = true; refresh();}, {signal});
    button.addEventListener('focusout', e => {focused = button.contains(e.relatedTarget); refresh();}, {signal});
    button.addEventListener('click', e => {
      const part = e.target.closest('[data-part]')?.dataset.part;
      if (!reactions[part]) return;
      play(reactions[part][0]);
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
  document.addEventListener('visibilitychange', () => {reset();}, {signal});
  document.addEventListener('scroll', reset, {capture:true, passive:true, signal});
  media.addEventListener('change', reset, {signal});
  const observer = new MutationObserver(bind);
  observer.observe(document.body, {childList:true, subtree:true});
  signal.addEventListener('abort', () => {reset(); cancelAnimationFrame(frame); observer.disconnect();});
  bind();
})();
