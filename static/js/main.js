/* main.js — The Royal Gym */

/* ===== Sticky navbar shadow ===== */
const navbar = document.getElementById('navbar');
if (navbar) {
    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > 8);
    });
}

/* ===== Mobile hamburger menu ===== */
const hamburger = document.getElementById('navHamburger');
const navLinks  = document.getElementById('navLinks');

if (hamburger && navLinks) {
    hamburger.addEventListener('click', () => {
        const open = navLinks.classList.toggle('open');
        hamburger.setAttribute('aria-expanded', String(open));
    });

    document.addEventListener('click', (e) => {
        if (navbar && !navbar.contains(e.target)) {
            navLinks.classList.remove('open');
            hamburger.setAttribute('aria-expanded', 'false');
        }
    });
}

/* ===== Flash messages: close button + auto-dismiss ===== */
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.flash-close');
    if (btn && btn.parentElement) {
        btn.parentElement.remove();
    }
});

document.querySelectorAll('.flash').forEach((flash) => {
    setTimeout(() => {
        flash.style.transition = 'opacity .5s ease';
        flash.style.opacity    = '0';
        setTimeout(() => flash.remove(), 520);
    }, 5000);
});

/* ===== Smooth scroll for in-page anchor links ===== */
document.querySelectorAll('a[href^="#"]').forEach((a) => {
    const href = a.getAttribute('href');
    if (!href || href.length <= 1) return;
    a.addEventListener('click', (e) => {
        const target = document.querySelector(href);
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

/* ===== Form validation helpers ===== */
function showError(input, msg) {
    clearError(input);
    input.style.borderColor = '#ef4444';
    input.focus();

    const err = document.createElement('p');
    err.className = 'validation-msg';
    err.textContent = msg;
    input.closest('.input-wrap').after(err);

    if (input.dataset.errorListener !== '1') {
        input.dataset.errorListener = '1';
        input.addEventListener('input', () => {
            clearError(input);
            input.dataset.errorListener = '0';
        }, { once: true });
    }
}

function clearError(input) {
    input.style.borderColor = '';
    const group = input.closest('.form-group');
    const existing = group && group.querySelector('.validation-msg');
    if (existing) existing.remove();
}

function validateEmail(val) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
}

function validateMobile(val) {
    return /^[\d\s+()\-]{7,20}$/.test(val);
}

/* ===== Enquiry form ===== */
const enquiryForm = document.getElementById('enquiryForm');
if (enquiryForm) {
    enquiryForm.addEventListener('submit', (e) => {
        let ok = true;
        const name    = enquiryForm.querySelector('[name="name"]');
        const message = enquiryForm.querySelector('[name="message"]');
        const email   = enquiryForm.querySelector('[name="email"]');
        const mobile  = enquiryForm.querySelector('[name="mobile"]');

        if (!name.value.trim()) {
            showError(name, 'Name is required.');
            ok = false;
        }
        if (email.value.trim() && !validateEmail(email.value.trim())) {
            showError(email, 'Please enter a valid email address.');
            ok = false;
        }
        if (mobile.value.trim() && !validateMobile(mobile.value.trim())) {
            showError(mobile, 'Please enter a valid mobile number.');
            ok = false;
        }
        if (!message.value.trim()) {
            showError(message, 'Message is required.');
            ok = false;
        }
        if (!ok) e.preventDefault();
    });
}

/* ===== Login form ===== */
const loginForm = document.getElementById('loginForm');
if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
        let ok = true;
        const email    = loginForm.querySelector('[name="email"]');
        const password = loginForm.querySelector('[name="password"]');

        if (!email.value.trim()) { showError(email, 'Email or username is required.'); ok = false; }
        if (!password.value)     { showError(password, 'Password is required.'); ok = false; }

        if (!ok) e.preventDefault();
    });
}

/* ===== Confirm-on-submit guard for destructive forms ===== */
document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (e) => {
        if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
});

/* ===== Members list: search + date-range filter ===== */
(function () {
    const tbody       = document.querySelector('.members-table tbody');
    const searchInput = document.getElementById('memberSearch');
    const fromInput   = document.getElementById('memberFrom');
    const toInput     = document.getElementById('memberTo');
    const expiryInput = document.getElementById('memberExpiry');
    const resetBtn    = document.getElementById('memberFilterReset');
    const emptyRow    = document.getElementById('memberSearchEmpty');
    const dateError   = document.getElementById('memberDateError');
    if (!tbody || (!searchInput && !fromInput && !toInput && !expiryInput)) return;

    const rows = Array.from(tbody.querySelectorAll('tr.member-row'));
    if (rows.length === 0) return;

    const digitsOnly = (s) => (s || '').replace(/\D/g, '');

    const RX_DATE = /^\d{4}-\d{2}-\d{2}$/;

    function applyFilter() {
        const q          = (searchInput?.value || '').trim().toLowerCase();
        const qDigits    = digitsOnly(q);
        const fromVal    = fromInput?.value   || '';
        const toVal      = toInput?.value     || '';
        const expiryRaw  = expiryInput?.value || '';
        const expiryVal  = RX_DATE.test(expiryRaw) ? expiryRaw : '';

        const dateInvalid = !!(fromVal && toVal && fromVal > toVal);
        if (dateError) {
            dateError.textContent = dateInvalid
                ? 'End date must be on or after start date.'
                : '';
        }
        [fromInput, toInput].forEach((el) => {
            if (el) el.classList.toggle('is-invalid', dateInvalid);
        });

        let visible = 0;
        rows.forEach((row) => {
            if (dateInvalid) { row.hidden = true; return; }

            const name   = row.dataset.searchName   || '';
            const mobile = row.dataset.searchMobile || '';
            const join   = row.dataset.joinDate     || '';
            const expire = row.dataset.expireDate   || '';

            let matchesQuery = !q;
            if (q) {
                if (name.includes(q)) matchesQuery = true;
                if (qDigits && qDigits.length >= 2 && mobile.includes(qDigits)) matchesQuery = true;
            }

            let inRange = true;
            if (fromVal && (!join || join < fromVal)) inRange = false;
            if (toVal   && (!join || join > toVal))   inRange = false;

            let matchesExpiry = true;
            if (expiryVal && expire !== expiryVal) matchesExpiry = false;

            const show = matchesQuery && inRange && matchesExpiry;
            row.hidden = !show;
            if (show) visible++;
        });

        if (emptyRow) emptyRow.hidden = visible > 0 || dateInvalid;
    }

    [searchInput, fromInput, toInput, expiryInput].forEach((el) => {
        if (!el) return;
        el.addEventListener('input',  applyFilter);
        el.addEventListener('change', applyFilter);
    });

    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            if (fromInput)   fromInput.value   = '';
            if (toInput)     toInput.value     = '';
            if (expiryInput) expiryInput.value = '';
            if (dateError)   dateError.textContent = '';
            [fromInput, toInput].forEach((el) => el && el.classList.remove('is-invalid'));
            applyFilter();
            if (searchInput) searchInput.focus();
        });
    }
})();

/* ===== Settings page: name/email filter ===== */
(function () {
    const search = document.getElementById('userSearch');
    if (!search) return;
    const rows = Array.from(document.querySelectorAll('tr.user-row'));
    if (rows.length === 0) return;
    const empty = document.getElementById('userSearchEmpty');

    function applyFilter() {
        const q = (search.value || '').trim().toLowerCase();
        let visible = 0;
        rows.forEach((row) => {
            const name  = row.dataset.searchName  || '';
            const email = row.dataset.searchEmail || '';
            const show = !q || name.includes(q) || email.includes(q);
            row.hidden = !show;
            if (show) visible++;
        });
        if (empty) empty.hidden = visible > 0;
    }

    search.addEventListener('input',  applyFilter);
    search.addEventListener('change', applyFilter);
})();

/* ===== Members list: delete confirmation modal ===== */
(function () {
    const modal = document.getElementById('deleteMemberModal');
    const form  = document.getElementById('deleteMemberForm');
    if (!modal || !form) return;

    const nameEl  = modal.querySelector('#deleteMemberName');
    const emailEl = modal.querySelector('#deleteMemberEmail');
    const supportsDialog = typeof modal.showModal === 'function';

    function openModal() {
        if (supportsDialog) {
            modal.showModal();
        } else {
            modal.setAttribute('open', '');
        }
    }

    function closeModal() {
        if (supportsDialog && modal.open) {
            modal.close();
        } else {
            modal.removeAttribute('open');
        }
    }

    document.querySelectorAll('[data-delete-member-id]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const id    = btn.dataset.deleteMemberId;
            const name  = btn.dataset.deleteMemberName  || 'this member';
            const email = btn.dataset.deleteMemberEmail || '';
            form.setAttribute('action', '/admin/members/' + encodeURIComponent(id) + '/delete');
            if (nameEl)  nameEl.textContent  = name;
            if (emailEl) emailEl.textContent = email;
            openModal();
        });
    });

    modal.querySelectorAll('[data-modal-close]').forEach((el) => {
        el.addEventListener('click', closeModal);
    });

    /* Click on the dialog's backdrop closes it. */
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });
})();

/* ===== Add Member form: inline validation, +91 mobile masking, submit gating ===== */
(function () {
    const form = document.getElementById('addMemberForm');
    if (!form) return;

    const submitBtn = document.getElementById('addMemberSubmit');
    const fields = Array.from(form.querySelectorAll('[data-validate]'));

    const RX_USERNAME      = /^\S{4,50}$/;
    const RX_EMAIL         = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const RX_INDIAN_MOBILE = /^\+91[6-9]\d{9}$/;
    const RX_DATE          = /^\d{4}-\d{2}-\d{2}$/;
    const DEFAULT_DOMAIN   = '@theroyalgym.com';

    function setError(input, msg) {
        const errorId = (input.getAttribute('aria-describedby') || '').split(' ')[0];
        const errorEl = errorId ? document.getElementById(errorId) : null;
        if (msg) {
            input.classList.add('is-invalid');
            input.setAttribute('aria-invalid', 'true');
            if (errorEl) errorEl.textContent = msg;
        } else {
            input.classList.remove('is-invalid');
            input.removeAttribute('aria-invalid');
            if (errorEl && !errorEl.dataset.serverMsg) errorEl.textContent = '';
        }
    }

    function validateField(input) {
        const kind = input.dataset.validate;
        const v = (input.value || '').trim();

        switch (kind) {
            case 'username': {
                if (!v) return 'Username is required.';
                if (!RX_USERNAME.test(v)) return 'Use 4–50 characters with no spaces.';
                const candidate = v.includes('@') ? v.toLowerCase() : (v.toLowerCase() + DEFAULT_DOMAIN);
                if (!RX_EMAIL.test(candidate)) return 'Username must form a valid email.';
                if (candidate.length > 150) return 'Username (after appending domain) is too long.';
                return '';
            }
            case 'password':
                if (!v) return 'Password is required.';
                if (v.length < 6) return 'Password must be at least 6 characters.';
                if (v.length > 200) return 'Password is too long.';
                return '';
            case 'name':
                if (!v) return 'Full name is required.';
                if (v.length < 2) return 'Full name is too short.';
                if (v.length > 100) return 'Full name is too long.';
                return '';
            case 'mobile':
                if (!v || v === '+91') return 'Mobile number is required.';
                if (!RX_INDIAN_MOBILE.test(v)) return 'Enter a valid Indian mobile: +91 followed by 10 digits starting 6–9.';
                return '';
            case 'age':
                if (!v) return '';
                if (!/^\d+$/.test(v)) return 'Age must be a whole number.';
                {
                    const n = parseInt(v, 10);
                    if (n < 5 || n > 120) return 'Age must be between 5 and 120.';
                }
                return '';
            case 'join_date':
                if (!v) return 'Join date is required.';
                if (!RX_DATE.test(v)) return 'Use a valid date (YYYY-MM-DD).';
                {
                    const d = new Date(v);
                    if (Number.isNaN(d.getTime())) return 'Use a valid date (YYYY-MM-DD).';
                }
                return '';
            case 'plan_id':
                if (!v) return 'Please select a membership plan.';
                return '';
            default:
                return '';
        }
    }

    function isFormValid() {
        return fields.every((input) => !validateField(input));
    }

    function refreshSubmit() {
        if (!submitBtn) return;
        const ok = isFormValid();
        submitBtn.disabled = !ok;
        submitBtn.setAttribute('aria-disabled', String(!ok));
    }

    /* Mobile masking: lock +91 prefix and only allow digits after it. */
    const mobile = form.querySelector('[data-validate="mobile"]');
    if (mobile) {
        const ensurePrefix = () => {
            if (!mobile.value.startsWith('+91')) {
                const digits = (mobile.value.match(/\d/g) || []).join('');
                mobile.value = '+91' + digits.replace(/^91/, '').slice(0, 10);
            } else {
                const tail = mobile.value.slice(3).replace(/\D/g, '').slice(0, 10);
                mobile.value = '+91' + tail;
            }
        };
        mobile.addEventListener('focus', () => {
            if (!mobile.value) mobile.value = '+91';
        });
        mobile.addEventListener('input', ensurePrefix);
        mobile.addEventListener('keydown', (e) => {
            // Block deletion of the +91 prefix.
            const start = mobile.selectionStart;
            const end = mobile.selectionEnd;
            const isDelete = e.key === 'Backspace' || e.key === 'Delete';
            if (isDelete && start <= 3 && end <= 3) {
                e.preventDefault();
                mobile.setSelectionRange(3, 3);
            }
        });
    }

    fields.forEach((input) => {
        const handler = () => {
            setError(input, input === document.activeElement ? '' : validateField(input));
            refreshSubmit();
        };
        input.addEventListener('input', () => {
            // Inline error clears as the user types; full check happens on blur.
            setError(input, '');
            refreshSubmit();
        });
        input.addEventListener('blur', handler);
        input.addEventListener('change', handler);
    });

    form.addEventListener('submit', (e) => {
        let firstInvalid = null;
        fields.forEach((input) => {
            const msg = validateField(input);
            setError(input, msg);
            if (msg && !firstInvalid) firstInvalid = input;
        });
        if (firstInvalid) {
            e.preventDefault();
            firstInvalid.focus();
        }
    });

    refreshSubmit();
})();
