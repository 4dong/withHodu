// Persist the split independently of Streamlit reruns and page changes.
(function () {
    if (window._readerLayoutObserver) {
        window._readerLayoutMount();
        return;
    }
    let ratio = 50;
    try {
        const saved = Number(localStorage.getItem('hodu.reader.split') || 50);
        if (Number.isFinite(saved)) ratio = Math.max(20, Math.min(80, saved));
    } catch (_) {}
    function mount() {
        const row = document.querySelector('.st-key-reader_split [data-testid="stHorizontalBlock"]');
        if (!row) return;
        const columns = Array.from(row.children).filter(el => el.matches('[data-testid="stColumn"]'));
        if (columns.length !== 2) return;
        function apply(value) {
            ratio = Math.max(20, Math.min(80, value));
            row.style.setProperty('--reader-split', ratio + '%');
            handle.setAttribute('aria-valuenow', String(Math.round(ratio)));
            handle.setAttribute('aria-valuetext', '원문 ' + Math.round(ratio) + '%, 번역 ' + Math.round(100 - ratio) + '%');
        }
        let handle = row.querySelector('.reader-split-handle');
        if (handle) return;
        handle = document.createElement('div');
        handle.className = 'reader-split-handle';
        handle.tabIndex = 0;
        handle.setAttribute('role', 'separator');
        handle.setAttribute('aria-label', '원문과 번역 너비 조절');
        handle.setAttribute('aria-orientation', 'vertical');
        handle.setAttribute('aria-valuemin', '20');
        handle.setAttribute('aria-valuemax', '80');
        handle.title = '드래그 또는 방향키로 너비 조절 · 두 번 클릭하면 반반';
        row.appendChild(handle);
        apply(ratio);
        function save() {
            try { localStorage.setItem('hodu.reader.split', String(ratio)); } catch (_) {}
        }
        handle.addEventListener('pointerdown', event => {
            if (event.button !== 0) return;
            event.preventDefault();
            handle.focus();
            handle.setPointerCapture(event.pointerId);
            row.classList.add('reader-resizing');
        });
        handle.addEventListener('pointermove', event => {
            if (!handle.hasPointerCapture(event.pointerId)) return;
            const bounds = row.getBoundingClientRect();
            apply(100 * (event.clientX - bounds.left) / bounds.width);
        });
        function finish() { row.classList.remove('reader-resizing'); save(); }
        handle.addEventListener('pointerup', event => {
            if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
            finish();
        });
        handle.addEventListener('lostpointercapture', finish);
        handle.addEventListener('pointercancel', finish);
        handle.addEventListener('dblclick', () => { apply(50); save(); });
        handle.addEventListener('keydown', event => {
            const values = {ArrowLeft: ratio - 2, ArrowRight: ratio + 2, Home: 20, End: 80};
            if (!(event.key in values)) return;
            event.preventDefault(); apply(values[event.key]); save();
        });
    }
    window._readerLayoutMount = mount;
    // Streamlit replaces panes when changing pages or reading modes.
    window._readerLayoutObserver = new MutationObserver(mount);
    window._readerLayoutObserver.observe(document.body, {childList: true, subtree: true});
    mount();
})();
