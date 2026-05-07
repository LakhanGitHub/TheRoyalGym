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

        if (!email.value.trim())    { showError(email, 'Email address is required.'); ok = false; }
        else if (!validateEmail(email.value.trim())) { showError(email, 'Please enter a valid email.'); ok = false; }
        if (!password.value)        { showError(password, 'Password is required.'); ok = false; }

        if (!ok) e.preventDefault();
    });
}

/* ===== Confirm-on-submit guard for destructive forms ===== */
document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (e) => {
        if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
});
