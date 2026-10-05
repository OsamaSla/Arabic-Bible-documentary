/**
 * Study ruler — multi-stage bottom toolbar.
 * Stage A (global): theme, back-to-top, share, view settings.
 * Stage B (commentary): + chapter nav, study tools, utilities.
 * Stage C: each tool shows only when its backing content exists.
 * CSP-safe: no inline handlers; progressive enhancement (no-JS = no ruler).
 */
(function () {
    'use strict';

    var RULER_VERSION = '1.1.0';
    var LS_PREFIX = 'ruler.';
    var BASE_H = 34;

    function lsGet(key, fallback) {
        try {
            var v = window.localStorage.getItem(LS_PREFIX + key);
            return v === null || v === undefined ? fallback : v;
        } catch (e) {
            return fallback;
        }
    }

    function lsSet(key, value) {
        try {
            window.localStorage.setItem(LS_PREFIX + key, value);
        } catch (e) { /* ignore */ }
    }

    function el(tag, cls, text) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (text !== undefined && text !== null) n.textContent = text;
        return n;
    }

    function article() {
        return document.querySelector('.document-layout > .document-content, article.document-content');
    }

    function pager() {
        try {
            return window.__docPager || null;
        } catch (e) {
            return null;
        }
    }

    /* ---------------- state ---------------- */

    var state = {
        fs: parseInt(lsGet('fs', '0'), 10) || 0,        // 0 = default, 1..5
        lh: parseInt(lsGet('lh', '0'), 10) || 0,        // 0 = default, 1..3
        width: lsGet('width', ''),                       // '' | compact | normal | wide
        mode: lsGet('mode', ''),                         // '' | comfortable | study | minimal
        hideNotes: lsGet('hideNotes', '0') === '1',
        hideFnRefs: lsGet('hideFnRefs', '0') === '1',
        hideRefs: lsGet('hideRefs', '0') === '1',
        hideVerses: lsGet('hideVerses', '0') === '1',
        focus: lsGet('focus', '0') === '1'
    };

    function applyState() {
        var b = document.body;
        var i;
        for (i = 1; i <= 5; i++) b.classList.remove('r-fs-' + i);
        for (i = 1; i <= 3; i++) b.classList.remove('r-lh-' + i);
        b.classList.remove('r-w-compact', 'r-w-normal', 'r-w-wide');
        b.classList.remove('r-mode-comfortable', 'r-mode-study', 'r-mode-minimal');
        if (state.fs >= 1 && state.fs <= 5) b.classList.add('r-fs-' + state.fs);
        if (state.lh >= 1 && state.lh <= 3) b.classList.add('r-lh-' + state.lh);
        if (state.width) b.classList.add('r-w-' + state.width);
        if (state.mode) b.classList.add('r-mode-' + state.mode);
        b.classList.toggle('r-hide-notes', state.hideNotes);
        b.classList.toggle('r-hide-fnrefs', state.hideFnRefs);
        b.classList.toggle('r-hide-refs', state.hideRefs);
        b.classList.toggle('r-hide-verses', state.hideVerses);
        b.classList.toggle('focus-mode', state.focus);
    }

    /* ---------------- context detection ---------------- */

    function detectContext() {
        var a = article();
        var hasToc = !!document.querySelector('.doc-toc a[href^="#"]');
        var headings = [];
        var footnotes = false;
        var notes = false;
        var verses = false;
        var refs = [];
        if (a) {
            var hNodes = a.querySelectorAll('h2, h3');
            var i, h;
            for (i = 0; i < hNodes.length; i++) {
                h = hNodes[i];
                // Skip headings inside footnotes/author-notes sections.
                if (h.closest && h.closest('.doc-footnotes, .doc-notes')) continue;
                if (!h.id) h.id = 'ruler-sec-' + (i + 1);
                var t = (h.textContent || '').replace(/\s+/g, ' ').trim();
                if (t) headings.push({ id: h.id, text: t });
            }
            footnotes = !!(a.querySelector('.doc-footnotes') ||
                a.querySelector('sup a[href^="#"], a[href^="#fn"]'));
            notes = !!a.querySelector('.doc-notes');
            verses = !!a.querySelector('.verse-num, .vnum');
            var seen = {};
            var links = a.querySelectorAll('a[href*="/bible/"], a[href*="bible/"]');
            for (i = 0; i < links.length; i++) {
                var href = links[i].getAttribute('href');
                var label = (links[i].textContent || '').replace(/\s+/g, ' ').trim() || href;
                if (href && !seen[href]) {
                    seen[href] = true;
                    refs.push({ href: href, label: label });
                }
            }
        }
        return {
            isCommentary: !!a,
            hasToc: hasToc,
            headings: headings,
            footnotes: footnotes,
            notes: notes,
            verses: verses,
            refs: refs
        };
    }

    /* ---------------- navigation helpers ---------------- */

    function gotoElement(target) {
        if (!target) return;
        try {
            var p = pager();
            if (p && p.mode === 'pages' && typeof p.pageOf === 'function' && typeof p.show === 'function') {
                var pi = p.pageOf(target);
                if (pi >= 0 && pi !== p.current) p.show(pi, true);
            }
            if (target.scrollIntoView) {
                try {
                    target.scrollIntoView({ block: 'start' });
                } catch (e) {
                    target.scrollIntoView();
                }
            }
        } catch (e) { /* ignore */ }
    }

    function tocEntries() {
        var out = [];
        var links = document.querySelectorAll('.doc-toc a[href^="#"]');
        for (var i = 0; i < links.length; i++) {
            var id = (links[i].getAttribute('href') || '').slice(1);
            if (!id) continue;
            var t = (links[i].textContent || '').replace(/\s+/g, ' ').trim();
            out.push({ id: id, text: t || id });
        }
        return out;
    }

    /* ---------------- highlight ---------------- */

    var hiState = { marks: [], idx: -1 };

    function clearHighlight(a) {
        var marks = a.querySelectorAll('mark.ruler-hit');
        for (var i = marks.length - 1; i >= 0; i--) {
            var m = marks[i];
            var parent = m.parentNode;
            if (!parent) continue;
            while (m.firstChild) parent.insertBefore(m.firstChild, m);
            parent.removeChild(m);
            try {
                parent.normalize();
            } catch (e) { /* ignore */ }
        }
        hiState.marks = [];
        hiState.idx = -1;
    }

    function runHighlight(a, query) {
        clearHighlight(a);
        query = (query || '').trim();
        if (!query || query.length < 2) return 0;
        var marks = [];
        var walker;
        try {
            walker = document.createTreeWalker(a, window.NodeFilter.SHOW_TEXT, null);
        } catch (e) {
            return 0;
        }
        var nodes = [];
        var n;
        while ((n = walker.nextNode())) {
            if (n.nodeValue && n.nodeValue.indexOf(query) !== -1) nodes.push(n);
        }
        nodes.forEach(function (textNode) {
            var val = textNode.nodeValue;
            var frag = document.createDocumentFragment();
            var pos = 0;
            var at;
            while ((at = val.indexOf(query, pos)) !== -1) {
                if (at > pos) frag.appendChild(document.createTextNode(val.slice(pos, at)));
                var mk = document.createElement('mark');
                mk.className = 'ruler-hit';
                mk.textContent = val.slice(at, at + query.length);
                frag.appendChild(mk);
                marks.push(mk);
                pos = at + query.length;
            }
            if (pos < val.length) frag.appendChild(document.createTextNode(val.slice(pos)));
            try {
                textNode.parentNode.replaceChild(frag, textNode);
            } catch (e) { /* ignore */ }
        });
        hiState.marks = marks;
        hiState.idx = -1;
        return marks.length;
    }

    function stepHighlight(dir, countEl) {
        if (!hiState.marks.length) return;
        hiState.idx = (hiState.idx + dir + hiState.marks.length) % hiState.marks.length;
        for (var i = 0; i < hiState.marks.length; i++) {
            hiState.marks[i].classList.toggle('is-current', i === hiState.idx);
        }
        var cur = hiState.marks[hiState.idx];
        gotoElement(cur);
        if (countEl) countEl.textContent = (hiState.idx + 1) + ' / ' + hiState.marks.length;
    }

    /* ---------------- bookmark ---------------- */

    function bookmarkKey() {
        try {
            return LS_PREFIX + 'bookmark.' + window.location.pathname;
        } catch (e) {
            return null;
        }
    }

    function readBookmark() {
        var k = bookmarkKey();
        if (!k) return null;
        try {
            var raw = window.localStorage.getItem(k);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    function saveBookmark() {
        var k = bookmarkKey();
        if (!k) return false;
        var p = pager();
        var data = {
            page: p && p.mode === 'pages' ? (p.current || 0) : 0,
            y: window.scrollY || window.pageYOffset || 0,
            at: Date.now()
        };
        try {
            window.localStorage.setItem(k, JSON.stringify(data));
            return true;
        } catch (e) {
            return false;
        }
    }

    function resumeBookmark() {
        var b = readBookmark();
        if (!b) return;
        var p = pager();
        try {
            if (p && p.mode === 'pages' && typeof p.show === 'function' && b.page > 0) {
                p.show(b.page, true);
            }
            window.scrollTo(0, b.y || 0);
        } catch (e) { /* ignore */ }
    }

    /* ---------------- builder ---------------- */

    // Android-style share mark (three connected dots); other buttons
    // use text glyphs. SVG allowed through as markup, glyphs as text.
    var SHARE_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg>';
    function makeBtn(action, icon, label, ariaLabel) {
        var b = el('button', 'ruler-btn');
        b.type = 'button';
        b.setAttribute('data-r', action);
        b.setAttribute('aria-label', ariaLabel || label);
        var ic = el('span', 'r-ico');
        ic.setAttribute('aria-hidden', 'true');
        if (icon === 'share-svg') ic.innerHTML = SHARE_SVG;
        else ic.textContent = icon;
        b.appendChild(ic);
        var lb = el('span', 'r-label', label);
        b.appendChild(lb);
        return b;
    }

    function chipRow(label, options, current, onPick) {
        var row = el('div', 'ruler-row');
        row.appendChild(el('span', 'ruler-label', label));
        options.forEach(function (opt) {
            var c = el('button', 'ruler-chip' + (opt.value === current ? ' is-active' : ''), opt.label);
            c.type = 'button';
            c.setAttribute('aria-pressed', opt.value === current ? 'true' : 'false');
            c.addEventListener('click', function () {
                onPick(opt.value);
                var sibs = row.querySelectorAll('.ruler-chip');
                for (var i = 0; i < sibs.length; i++) {
                    var on = sibs[i] === c;
                    sibs[i].classList.toggle('is-active', on);
                    sibs[i].setAttribute('aria-pressed', on ? 'true' : 'false');
                }
            });
            row.appendChild(c);
        });
        return row;
    }

    function switchRow(label, checked, onToggle) {
        var lab = el('label', 'ruler-switch');
        var input = document.createElement('input');
        input.type = 'checkbox';
        if (checked) input.checked = true;
        input.addEventListener('change', function () {
            onToggle(input.checked);
        });
        lab.appendChild(input);
        lab.appendChild(el('span', null, label));
        var row = el('div', 'ruler-row');
        row.appendChild(lab);
        return { row: row, input: input };
    }

    function linkList(items, onPickLink) {
        var ul = el('ul', 'ruler-link-list');
        items.forEach(function (it) {
            var li = document.createElement('li');
            if (it.href) {
                var a = document.createElement('a');
                a.href = it.href;
                a.textContent = it.text;
                a.setAttribute('target', '_blank');
                a.setAttribute('rel', 'noopener');
                li.appendChild(a);
            } else {
                var b = el('button', 'ruler-link', it.text);
                b.type = 'button';
                b.addEventListener('click', function () {
                    onPickLink(it);
                });
                li.appendChild(b);
            }
            ul.appendChild(li);
        });
        return ul;
    }

    var openPanelId = null;
    var panelRefs = {};

    function closePanels() {
        openPanelId = null;
        for (var id in panelRefs) {
            if (panelRefs.hasOwnProperty(id)) panelRefs[id].classList.remove('is-open');
        }
        var btns = document.querySelectorAll('#study-ruler [data-r][aria-expanded]');
        for (var i = 0; i < btns.length; i++) btns[i].setAttribute('aria-expanded', 'false');
    }

    function togglePanel(id, btn) {
        if (openPanelId === id) {
            closePanels();
            return;
        }
        closePanels();
        openPanelId = id;
        if (panelRefs[id]) panelRefs[id].classList.add('is-open');
        if (btn) btn.setAttribute('aria-expanded', 'true');
    }

    function build(ctx) {
        if (document.getElementById('study-ruler')) return;

        var root = el('div');
        root.id = 'study-ruler';

        var panels = el('div', 'ruler-panels');
        root.appendChild(panels);

        var base = el('div', 'ruler-base');
        base.setAttribute('role', 'toolbar');
        base.setAttribute('aria-label', 'شريط أدوات القراءة');
        root.appendChild(base);

        function addPanel(id) {
            var s = el('section', 'ruler-panel');
            s.id = id;
            s.setAttribute('role', 'dialog');
            s.setAttribute('aria-label', id);
            panels.appendChild(s);
            panelRefs[id] = s;
            return s;
        }

        function addBaseBtn(action, icon, label, panelId, hidden) {
            var b = makeBtn(action, icon, label);
            if (panelId) {
                b.setAttribute('aria-expanded', 'false');
                b.setAttribute('aria-controls', panelId);
                b.addEventListener('click', function () {
                    togglePanel(panelId, b);
                });
            }
            if (hidden) b.hidden = true;
            base.appendChild(b);
            return b;
        }

        /* ----- Stage A: global minimal tools ----- */
        var btnTheme = makeBtn('theme', '◐', 'المظهر', 'تبديل المظهر');
        btnTheme.addEventListener('click', function () {
            // Drive the existing header toggle so theme logic stays in one place.
            var t = document.getElementById('themeToggle');
            if (t) t.click();
        });
        base.appendChild(btnTheme);

        var btnTop = makeBtn('top', '↑', 'الأعلى', 'الصعود إلى الأعلى');
        btnTop.addEventListener('click', function () {
            try {
                window.scrollTo(0, 0);
            } catch (e) { /* ignore */ }
        });
        base.appendChild(btnTop);

        var a = article();
        var shareUrl = window.location.href;
        var shareTitle = document.title;
        if (a) {
            var h1 = document.querySelector('h1.document-title');
            if (h1) shareTitle = (h1.textContent || '').replace(/\s+/g, ' ').trim();
        }
        var btnShare = makeBtn('share', 'share-svg', 'مشاركة', 'مشاركة الصفحة');
        btnShare.setAttribute('data-action', 'share');
        btnShare.setAttribute('data-share-title', shareTitle);
        btnShare.setAttribute('data-share-url', shareUrl);
        base.appendChild(btnShare);

        var btnView = addBaseBtn('view', '◧', 'العرض', 'rpanel-view', false);

        /* ----- Stage B: commentary tools ----- */
        var btnPrev = null, btnNext = null, btnChapters = null,
            btnSections = null, btnStudy = null, btnTools = null;
        var tocIdx = 0;
        var tocList = tocEntries();

        function jumpToc(d) {
            if (!tocList.length) return;
            tocIdx = (tocIdx + d + tocList.length) % tocList.length;
            var target = document.getElementById(tocList[tocIdx].id);
            if (target) gotoElement(target);
        }

        if (ctx.isCommentary) {
            var sep = el('span', 'ruler-sep');
            sep.setAttribute('aria-hidden', 'true');
            base.appendChild(sep);

            if (ctx.hasToc && tocList.length > 1) {
                btnPrev = makeBtn('prev', '→', 'السابق', 'الفصل السابق');
                btnPrev.addEventListener('click', function () {
                    jumpToc(-1);
                });
                base.appendChild(btnPrev);
            }

            if (ctx.hasToc) {
                btnChapters = addBaseBtn('chapters', '☰', 'الفصول', 'rpanel-nav', false);
            }

            if (ctx.hasToc && tocList.length > 1) {
                btnNext = makeBtn('next', '←', 'التالي', 'الفصل التالي');
                btnNext.addEventListener('click', function () {
                    jumpToc(1);
                });
                base.appendChild(btnNext);
            }

            if (ctx.headings.length > 1) {
                btnSections = addBaseBtn('sections', '§', 'الأقسام', 'rpanel-sections', false);
            }

            btnStudy = addBaseBtn('study', '✎', 'دراسة', 'rpanel-study', false);
            btnTools = addBaseBtn('tools', '⋯', 'أدوات', 'rpanel-tools', false);

            // Resume-position chip (visible only when a bookmark exists).
            var resume = el('button', 'ruler-resume', '↩ عودة للموضع');
            resume.type = 'button';
            resume.setAttribute('aria-label', 'العودة إلى الموضع المحفوظ');
            if (readBookmark()) resume.classList.add('has-saved');
            resume.addEventListener('click', resumeBookmark);
            base.appendChild(resume);
            root.__resumeBtn = resume;
        }

        /* ----- Panels ----- */
        var pView = addPanel('rpanel-view');
        pView.setAttribute('aria-label', 'إعدادات العرض');
        pView.appendChild(chipRow('حجم الخط', [
            { value: 0, label: 'افتراضي' },
            { value: 1, label: 'صغير' },
            { value: 2, label: 'مريح' },
            { value: 3, label: 'كبير' },
            { value: 4, label: 'كبير+' },
            { value: 5, label: 'ضخم' }
        ], state.fs, function (v) {
            state.fs = v;
            lsSet('fs', String(v));
            applyState();
        }));
        pView.appendChild(chipRow('تباعد الأسطر', [
            { value: 0, label: 'افتراضي' },
            { value: 1, label: 'مضغوط' },
            { value: 2, label: 'مريح' },
            { value: 3, label: 'واسع' }
        ], state.lh, function (v) {
            state.lh = v;
            lsSet('lh', String(v));
            applyState();
        }));
        if (ctx.isCommentary) {
            pView.appendChild(chipRow('عرض الصفحة', [
                { value: '', label: 'عادي' },
                { value: 'compact', label: 'مضغوط' },
                { value: 'normal', label: 'متوسط' },
                { value: 'wide', label: 'واسع' }
            ], state.width, function (v) {
                state.width = v;
                lsSet('width', v);
                applyState();
            }));
            pView.appendChild(chipRow('وضع القراءة', [
                { value: '', label: 'افتراضي' },
                { value: 'comfortable', label: 'مريح' },
                { value: 'study', label: 'دراسة' },
                { value: 'minimal', label: 'مباشر' }
            ], state.mode, function (v) {
                state.mode = v;
                lsSet('mode', v);
                applyState();
            }));
            if (ctx.footnotes) {
                var sw1 = switchRow('إظهار الحواشي', !state.hideNotes, function (on) {
                    state.hideNotes = !on;
                    lsSet('hideNotes', state.hideNotes ? '1' : '0');
                    applyState();
                });
                pView.appendChild(sw1.row);
            }
            var sw2 = switchRow('إظهار المراجع', !state.hideRefs, function (on) {
                state.hideRefs = !on;
                lsSet('hideRefs', state.hideRefs ? '1' : '0');
                applyState();
            });
            pView.appendChild(sw2.row);
            if (ctx.verses) {
                var sw3 = switchRow('أرقام الآيات', !state.hideVerses, function (on) {
                    state.hideVerses = !on;
                    lsSet('hideVerses', state.hideVerses ? '1' : '0');
                    applyState();
                });
                pView.appendChild(sw3.row);
            }
            var swF = switchRow('وضع التركيز (إخفاء الهيدر)', state.focus, function (on) {
                state.focus = on;
                lsSet('focus', on ? '1' : '0');
                applyState();
            });
            pView.appendChild(swF.row);
        } else {
            var h = el('p', 'ruler-hint', 'إعدادات العرض الكاملة متاحة في صفحات التعليقات.');
            pView.appendChild(h);
        }

        if (ctx.isCommentary) {
            try {
            if (ctx.hasToc) {
                var pNav = addPanel('rpanel-nav');
                pNav.setAttribute('aria-label', 'التنقل بين الفصول');
                pNav.appendChild(el('h4', null, 'الفصول'));
                pNav.appendChild(linkList(tocList.map(function (t) {
                    return { text: t.text, id: t.id };
                }), function (it) {
                    var target = document.getElementById(it.id);
                    if (target) gotoElement(target);
                }));
                var rowTB = el('div', 'ruler-row');
                var bTop2 = el('button', 'ruler-chip', '↑ أعلى الصفحة');
                bTop2.type = 'button';
                bTop2.addEventListener('click', function () {
                    try {
                        window.scrollTo(0, 0);
                    } catch (e) { /* ignore */ }
                });
                var bBot = el('button', 'ruler-chip', '↓ أسفل الصفحة');
                bBot.type = 'button';
                bBot.addEventListener('click', function () {
                    try {
                        window.scrollTo(0, document.body.scrollHeight || 99999);
                    } catch (e) { /* ignore */ }
                });
                rowTB.appendChild(bTop2);
                rowTB.appendChild(bBot);
                pNav.appendChild(rowTB);
            }

            if (ctx.headings.length > 1) {
                var pSec = addPanel('rpanel-sections');
                pSec.setAttribute('aria-label', 'أقسام المقال');
                pSec.appendChild(el('h4', null, 'أقسام المقال'));
                pSec.appendChild(linkList(ctx.headings.map(function (hh) {
                    return { text: hh.text, id: hh.id };
                }), function (it) {
                    var target = document.getElementById(it.id);
                    if (target) gotoElement(target);
                }));
            }

            var pStudy = addPanel('rpanel-study');
            pStudy.setAttribute('aria-label', 'أدوات الدراسة');
            // NOTE: the headings index lives only in the أقسام panel;
            // study keeps highlight, parallel refs and author notes.

            if (ctx.refs.length) {
                pStudy.appendChild(el('h4', null, 'عرض موازٍ (شواهد كتابية)'));
                pStudy.appendChild(linkList(ctx.refs.map(function (r) {
                    return { text: r.label, href: r.href };
                }), null));
            }

            pStudy.appendChild(el('h4', null, 'تمييز الكلمات'));
            var hiRow = el('div', 'ruler-row');
            var hiInput = el('input', 'ruler-input');
            hiInput.type = 'search';
            hiInput.setAttribute('placeholder', 'كلمة للتمييز…');
            hiInput.setAttribute('aria-label', 'كلمة للتمييز');
            var hiCount = el('span', 'ruler-hint', '');
            var hiGo = el('button', 'ruler-chip', 'تمييز');
            hiGo.type = 'button';
            hiGo.addEventListener('click', function () {
                var n = runHighlight(article(), hiInput.value);
                hiCount.textContent = n ? ('1 / ' + n) : (hiInput.value.trim().length >= 2 ? 'لا نتائج' : '');
                if (n) stepHighlight(1, hiCount);
            });
            hiInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    hiGo.click();
                }
            });
            var hiPrev = el('button', 'ruler-chip', '→');
            hiPrev.type = 'button';
            hiPrev.setAttribute('aria-label', 'النتيجة السابقة');
            hiPrev.addEventListener('click', function () {
                stepHighlight(-1, hiCount);
            });
            var hiNext = el('button', 'ruler-chip', '←');
            hiNext.type = 'button';
            hiNext.setAttribute('aria-label', 'النتيجة التالية');
            hiNext.addEventListener('click', function () {
                stepHighlight(1, hiCount);
            });
            var hiClear = el('button', 'ruler-chip', 'مسح');
            hiClear.type = 'button';
            hiClear.addEventListener('click', function () {
                clearHighlight(article());
                hiCount.textContent = '';
                hiInput.value = '';
            });
            hiRow.appendChild(hiInput);
            hiRow.appendChild(hiGo);
            hiRow.appendChild(hiPrev);
            hiRow.appendChild(hiNext);
            hiRow.appendChild(hiClear);
            hiRow.appendChild(hiCount);
            pStudy.appendChild(hiRow);

            if (ctx.notes) {
                var swN = switchRow('ملاحظات المؤلف', !state.hideNotes, function (on) {
                    state.hideNotes = !on;
                    lsSet('hideNotes', state.hideNotes ? '1' : '0');
                    applyState();
                });
                pStudy.appendChild(swN.row);
            }

            var pTools = addPanel('rpanel-tools');
            pTools.setAttribute('aria-label', 'أدوات');
            var tRow = el('div', 'ruler-row');
            var dlUrl = a.getAttribute('data-download-url');
            if (dlUrl) {
                var dl = document.createElement('a');
                dl.className = 'ruler-chip';
                dl.href = dlUrl;
                dl.setAttribute('download', '');
                dl.textContent = '⤓ تحميل';
                tRow.appendChild(dl);
            }
            var bPrint = el('button', 'ruler-chip', '🖨 طباعة');
            bPrint.type = 'button';
            bPrint.setAttribute('data-action', 'print');
            tRow.appendChild(bPrint);
            var bShare2 = el('button', 'ruler-chip');
            bShare2.innerHTML = SHARE_SVG + ' <span>مشاركة</span>';
            bShare2.type = 'button';
            bShare2.setAttribute('data-action', 'share');
            bShare2.setAttribute('data-share-title', shareTitle);
            bShare2.setAttribute('data-share-url', shareUrl);
            tRow.appendChild(bShare2);
            var bCopy = el('button', 'ruler-chip', '⧉ نسخ النص');
            bCopy.type = 'button';
            bCopy.setAttribute('data-action', 'copy-text');
            tRow.appendChild(bCopy);
            var bMark = el('button', 'ruler-chip', '🔖 حفظ الموضع');
            bMark.type = 'button';
            bMark.addEventListener('click', function () {
                var ok = saveBookmark();
                bMark.textContent = ok ? '✓ تم الحفظ' : 'تعذر الحفظ';
                if (root.__resumeBtn && ok) root.__resumeBtn.classList.add('has-saved');
                setTimeout(function () {
                    bMark.textContent = '🔖 حفظ الموضع';
                }, 2000);
            });
            tRow.appendChild(bMark);
            pTools.appendChild(tRow);
            pTools.appendChild(el('p', 'ruler-hint', 'حفظ الموضع يتذكر الصفحة والموضع في هذا المتصفح.'));
            } catch (err) {
                try {
                    if (window.console && window.console.warn) {
                        window.console.warn('[ruler] panel build failed', err);
                    }
                } catch (e) { /* ignore */ }
            }
        }

        try {
            root.setAttribute('data-ruler-version', RULER_VERSION);
        } catch (e) { /* ignore */ }
        document.body.appendChild(root);
        try {
            document.body.classList.add('has-ruler');
        } catch (e) { /* ignore */ }
        try {
            if (window.console && window.console.info) {
                window.console.info('[ruler] v' + RULER_VERSION +
                    ' mode=' + (ctx.isCommentary ? 'commentary' : 'global'));
            }
        } catch (e) { /* ignore */ }

        // Keep the layout offset in sync with the real bar height.
        try {
            var h = base.getBoundingClientRect().height || BASE_H;
            document.documentElement.style.setProperty('--ruler-h', Math.ceil(h) + 'px');
        } catch (e) { /* keep default */ }

        // Close on outside click / ESC.
        document.addEventListener('click', function (e) {
            if (!openPanelId) return;
            if (e.target && e.target.closest && e.target.closest('#study-ruler')) return;
            closePanels();
        }, true);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && openPanelId) closePanels();
        });
    }

    function refreshContext() {
        // Pager rebuilds (load / fonts.ready) can change the DOM: re-detect.
        // Cheap single-pass query; only rebuilds the ruler if commentary
        // tools newly qualify (prevents an unqualified bar from lingering).
        try {
            var root = document.getElementById('study-ruler');
            if (!root) {
                build(detectContext());
                return;
            }
        } catch (e) { /* ignore */ }
    }

    function init() {
        applyState();
        build(detectContext());
        window.addEventListener('load', refreshContext);
        try {
            window.__rulerDiag = function () {
                var a = article();
                var cs = null;
                try {
                    cs = a ? window.getComputedStyle(a).fontSize : null;
                } catch (e) { cs = null; }
                return {
                    version: RULER_VERSION,
                    mounted: !!document.getElementById('study-ruler'),
                    openPanel: openPanelId,
                    bodyClasses: document.body.className,
                    articleFontSize: cs,
                    state: state
                };
            };
        } catch (e) { /* ignore */ }
    }

    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    }
})();
