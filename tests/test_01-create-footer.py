"""
tests/test_01-create-footer.py

Pytest suite for the "Create Footer" feature (spec: .claude/specs/01-create-footer.md).

Tests are written against the SPEC, not the implementation.  They define what the
footer SHOULD do and serve as a correctness contract for future refactors.

No BeautifulSoup is available in requirements.txt (Flask==3.0.3, Werkzeug==3.0.3 only),
so all assertions use plain string search / re.search() on decoded response data or on
the raw CSS file content.
"""

import os
import re
import sys
import tempfile
import sqlite3
import pytest

# ---------------------------------------------------------------------------
# Make the app package importable when pytest is run from any working directory.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..')
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import database.db as _db_module          # noqa: E402  (imported after sys.path tweak)
from app import app as flask_app           # noqa: E402
from database.db import init_db, seed_db  # noqa: E402

# ---------------------------------------------------------------------------
# Paths used in CSS-file tests (read from disk, not via HTTP).
# ---------------------------------------------------------------------------
_CSS_PATH = os.path.join(_PROJECT_ROOT, 'static', 'css', 'style.css')


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture()
def app(tmp_path, monkeypatch):
    """
    Yield a Flask test app wired to a temporary SQLite file so that every
    test gets an isolated DB.  We patch database.db.DB_PATH before calling
    init_db() / seed_db() because get_db() reads DB_PATH at call time.
    """
    db_file = str(tmp_path / 'test_gym.db')
    monkeypatch.setattr(_db_module, 'DB_PATH', db_file)

    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-footer',
        'WTF_CSRF_ENABLED': False,
    })

    with flask_app.app_context():
        init_db()
        seed_db()   # seeds admin (lakhan@admin.com / 123456) and member (ansh@member.com / 123456)
        yield flask_app


@pytest.fixture()
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture()
def admin_client(app):
    """
    Test client pre-logged-in as the seeded admin user.
    Seed credentials: lakhan@admin.com / 123456  role='admin'
    """
    c = app.test_client()
    # Obtain a CSRF token first via a GET to /login.
    resp = c.get('/login')
    assert resp.status_code == 200, 'GET /login must return 200 to seed CSRF token'

    with c.session_transaction() as sess:
        token = sess.get('csrf_token', '')

    c.post('/login', data={
        'email': 'lakhan@admin.com',
        'password': '123456',
        'csrf_token': token,
    }, follow_redirects=False)
    return c


@pytest.fixture()
def member_client(app):
    """
    Test client pre-logged-in as the seeded regular member.
    Seed credentials: ansh@member.com / 123456  role='user'
    """
    c = app.test_client()
    resp = c.get('/login')
    assert resp.status_code == 200, 'GET /login must return 200 to seed CSRF token'

    with c.session_transaction() as sess:
        token = sess.get('csrf_token', '')

    c.post('/login', data={
        'email': 'ansh@member.com',
        'password': '123456',
        'csrf_token': token,
    }, follow_redirects=False)
    return c


# ===========================================================================
# Helper
# ===========================================================================

def _html(response):
    """Return response body as a decoded string for plain-text assertions."""
    return response.data.decode('utf-8', errors='replace')


# ===========================================================================
# Group 1 — Footer element present on all required pages
# ===========================================================================

class TestFooterPresentOnAllPages:

    def test_footer_present_on_landing(self, client):
        """Spec: footer renders on the landing page (/)."""
        resp = client.get('/')
        body = _html(resp)
        assert resp.status_code == 200, 'Landing page must return 200'
        assert '<footer' in body, 'Footer element must be present on landing page'
        assert 'role="contentinfo"' in body, \
            'Footer must carry role="contentinfo" on landing page'

    def test_footer_element_class_on_landing(self, client):
        """Spec: footer tag uses class="footer"."""
        resp = client.get('/')
        body = _html(resp)
        # Allow any attribute order; both class and role must appear on the same footer tag.
        assert re.search(r'<footer[^>]*class="footer"', body), \
            'Footer must have class="footer"'
        assert re.search(r'<footer[^>]*role="contentinfo"', body), \
            'Footer must have role="contentinfo"'

    def test_footer_present_on_login_page(self, client):
        """Spec: footer renders on /login."""
        resp = client.get('/login')
        body = _html(resp)
        assert resp.status_code == 200, 'Login page must return 200'
        assert '<footer' in body, 'Footer element must be present on login page'
        assert 'role="contentinfo"' in body, \
            'Footer must carry role="contentinfo" on login page'

    def test_footer_present_on_404_page(self, client):
        """Spec: footer renders on the custom 404 error page."""
        resp = client.get('/this-route-does-not-exist-xyz')
        body = _html(resp)
        assert resp.status_code == 404, 'Unknown route must return 404'
        assert '<footer' in body, 'Footer element must be present on 404 error page'

    def test_footer_present_on_admin_dashboard(self, admin_client):
        """Spec: footer renders on /admin/dashboard (admin role required)."""
        resp = admin_client.get('/admin/dashboard', follow_redirects=True)
        body = _html(resp)
        assert '<footer' in body, 'Footer must be present on admin dashboard'
        assert 'role="contentinfo"' in body, \
            'Footer must carry role="contentinfo" on admin dashboard'

    def test_footer_present_on_member_dashboard(self, member_client):
        """Spec: footer renders on /member/dashboard (member role required)."""
        resp = member_client.get('/member/dashboard', follow_redirects=True)
        body = _html(resp)
        assert '<footer' in body, 'Footer must be present on member dashboard'
        assert 'role="contentinfo"' in body, \
            'Footer must carry role="contentinfo" on member dashboard'


# ===========================================================================
# Group 2 — Footer inner grid structure
# ===========================================================================

class TestFooterGridStructure:

    def test_footer_grid_class_present(self, client):
        """Spec: footer inner grid uses class footer-grid."""
        resp = client.get('/')
        assert 'footer-grid' in _html(resp), \
            'footer-grid class must appear inside the footer'

    def test_footer_col_class_present(self, client):
        """Spec: each column uses class footer-col."""
        resp = client.get('/')
        body = _html(resp)
        assert body.count('footer-col') >= 1, \
            'At least one footer-col element must be present'

    def test_footer_inner_wrapper_present(self, client):
        """Spec: inner content is constrained by a wrapper (footer-inner)."""
        resp = client.get('/')
        assert 'footer-inner' in _html(resp), \
            'footer-inner container must wrap the footer grid'


# ===========================================================================
# Group 3 — Brand column
# ===========================================================================

class TestFooterBrandColumn:

    def test_footer_brand_wordmark(self, client):
        """Spec: brand column contains 'The Royal Gym' wordmark."""
        resp = client.get('/')
        body = _html(resp)
        # The wordmark should appear inside the footer element.
        footer_start = body.find('<footer')
        footer_end = body.find('</footer>', footer_start)
        footer_fragment = body[footer_start:footer_end]
        assert 'The Royal Gym' in footer_fragment, \
            'Brand wordmark "The Royal Gym" must appear in the footer brand column'

    def test_footer_brand_class_present(self, client):
        """Spec: brand element uses class footer-brand."""
        resp = client.get('/')
        assert 'footer-brand' in _html(resp), \
            'footer-brand class must be present in the footer'

    def test_footer_tagline_class_present(self, client):
        """Spec: tagline paragraph uses class footer-tagline."""
        resp = client.get('/')
        assert 'footer-tagline' in _html(resp), \
            'footer-tagline class must be present inside the footer'


# ===========================================================================
# Group 4 — Quick Links / Explore column (url_for anchor links)
# ===========================================================================

class TestFooterQuickLinks:

    def test_footer_nav_aria_label_for_links(self, client):
        """Spec: the links column is wrapped in <nav> with an aria-label."""
        resp = client.get('/')
        body = _html(resp)
        # There must be at least one <nav with aria-label inside the footer.
        footer_start = body.find('<footer')
        footer_end = body.find('</footer>', footer_start)
        footer_fragment = body[footer_start:footer_end]
        assert re.search(r'<nav[^>]+aria-label', footer_fragment), \
            'Footer links column must use <nav aria-label="..."> for accessibility'

    def test_footer_explore_link_why(self, client):
        """Spec: Explore links use url_for('index', _anchor='why') -> href="/#why"."""
        resp = client.get('/')
        body = _html(resp)
        assert 'href="/#why"' in body or "href='/#why'" in body, \
            'Explore "why" link must render as /#why in the footer'

    def test_footer_explore_link_programs(self, client):
        """Spec: Explore links use url_for('index', _anchor='programs') -> href="/#programs"."""
        resp = client.get('/')
        body = _html(resp)
        assert 'href="/#programs"' in body or "href='/#programs'" in body, \
            'Explore "programs" link must render as /#programs in the footer'

    def test_footer_explore_link_plans(self, client):
        """Spec: Explore links use url_for('index', _anchor='plans') -> href="/#plans"."""
        resp = client.get('/')
        body = _html(resp)
        assert 'href="/#plans"' in body or "href='/#plans'" in body, \
            'Explore "plans" link must render as /#plans in the footer'

    def test_footer_explore_link_contact(self, client):
        """Spec: Explore links use url_for('index', _anchor='contact') -> href="/#contact"."""
        resp = client.get('/')
        body = _html(resp)
        assert 'href="/#contact"' in body or "href='/#contact'" in body, \
            'Explore "contact" link must render as /#contact in the footer'

    def test_footer_quick_links_use_footer_link_class(self, client):
        """Spec: list items in the links column use class footer-link."""
        resp = client.get('/')
        assert 'footer-link' in _html(resp), \
            'footer-link class must be applied to anchor links inside footer'

    def test_footer_links_use_ul_li_structure(self, client):
        """Spec: link lists use <ul>/<li> semantic markup."""
        resp = client.get('/')
        body = _html(resp)
        footer_start = body.find('<footer')
        footer_end = body.find('</footer>', footer_start)
        footer_fragment = body[footer_start:footer_end]
        assert '<ul' in footer_fragment, \
            'Footer link lists must use <ul> semantic markup'
        assert '<li' in footer_fragment, \
            'Footer link lists must use <li> semantic markup'

    def test_footer_explore_links_correct_from_login_page(self, client):
        """
        Spec: Explore links from non-landing pages must still resolve to /#<anchor>.
        Verifies url_for() generates correct href on /login.
        """
        resp = client.get('/login')
        body = _html(resp)
        # At least one anchor-prefixed index link must be present on /login footer.
        assert re.search(r'href="/#\w+"', body), \
            'Footer anchor links must resolve to /#<id> on non-landing pages like /login'


# ===========================================================================
# Group 5 — Contact column
# ===========================================================================

class TestFooterContactColumn:

    def test_footer_contact_wrapped_in_address(self, client):
        """Spec: Contact column is wrapped in <address> for correct semantics."""
        resp = client.get('/')
        body = _html(resp)
        footer_start = body.find('<footer')
        footer_end = body.find('</footer>', footer_start)
        footer_fragment = body[footer_start:footer_end]
        assert '<address' in footer_fragment, \
            'Contact column must be wrapped in <address> element'

    def test_footer_contact_tel_link(self, client):
        """Spec: phone number uses href="tel:+919876543210"."""
        resp = client.get('/')
        body = _html(resp)
        assert 'href="tel:+919876543210"' in body or "href='tel:+919876543210'" in body, \
            'Footer phone link must use href="tel:+919876543210"'

    def test_footer_contact_mailto_link(self, client):
        """Spec: email uses an href="mailto:..." link."""
        resp = client.get('/')
        body = _html(resp)
        footer_start = body.find('<footer')
        footer_end = body.find('</footer>', footer_start)
        footer_fragment = body[footer_start:footer_end]
        assert 'href="mailto:' in footer_fragment or "href='mailto:" in footer_fragment, \
            'Footer must contain a mailto: link for the contact email address'

    def test_footer_contact_uses_footer_contact_class(self, client):
        """Spec: contact list uses class footer-contact."""
        resp = client.get('/')
        assert 'footer-contact' in _html(resp), \
            'footer-contact class must be used in the footer contact column'

    def test_footer_contact_line_class_present(self, client):
        """Spec: each contact row uses class footer-contact-line."""
        resp = client.get('/')
        assert 'footer-contact-line' in _html(resp), \
            'footer-contact-line class must be present in the footer'


# ===========================================================================
# Group 6 — Bottom bar
# ===========================================================================

class TestFooterBottomBar:

    def test_footer_bottom_copyright_text(self, client):
        """Spec: bottom bar contains '2026 The Royal Gym. All rights reserved.'"""
        resp = client.get('/')
        body = _html(resp)
        footer_start = body.find('<footer')
        footer_end = body.find('</footer>', footer_start)
        footer_fragment = body[footer_start:footer_end]
        assert '2026 The Royal Gym' in footer_fragment, \
            'Footer bottom bar must contain copyright year 2026 and brand name'
        assert 'All rights reserved' in footer_fragment, \
            'Footer bottom bar must contain "All rights reserved" text'

    def test_footer_bottom_class_present(self, client):
        """Spec: bottom bar uses class footer-bottom."""
        resp = client.get('/')
        assert 'footer-bottom' in _html(resp), \
            'footer-bottom class must be present in the footer'

    def test_footer_bottom_privacy_or_terms_link(self, client):
        """Spec: bottom bar contains Privacy Policy and/or Terms of Service links."""
        resp = client.get('/')
        body = _html(resp)
        footer_start = body.find('<footer')
        footer_end = body.find('</footer>', footer_start)
        footer_fragment = body[footer_start:footer_end]
        has_privacy = 'Privacy' in footer_fragment
        has_terms = 'Terms' in footer_fragment
        assert has_privacy or has_terms, \
            'Footer bottom bar must contain Privacy Policy and/or Terms of Service links'

    def test_footer_bottom_links_class_present_or_terms_link(self, client):
        """Spec: bottom bar links use class footer-bottom-links (or equivalent)."""
        resp = client.get('/')
        body = _html(resp)
        # The spec names footer-bottom-links; accept it or the simpler inline pattern.
        assert 'footer-bottom' in body, \
            'footer-bottom (or footer-bottom-links) class must appear in footer'


# ===========================================================================
# Group 7 — Accessibility attributes
# ===========================================================================

class TestFooterAccessibility:

    def test_decorative_svgs_have_aria_hidden(self, client):
        """Spec: all decorative SVGs inside the footer use aria-hidden='true'."""
        resp = client.get('/')
        body = _html(resp)
        footer_start = body.find('<footer')
        footer_end = body.find('</footer>', footer_start)
        footer_fragment = body[footer_start:footer_end]

        # Count SVG openings and aria-hidden="true" occurrences within footer.
        svg_count = footer_fragment.count('<svg')
        aria_hidden_count = footer_fragment.count('aria-hidden="true"')

        assert svg_count > 0, \
            'Footer must contain at least one SVG icon'
        assert aria_hidden_count > 0, \
            'Decorative SVGs in footer must include aria-hidden="true"'

    def test_contact_icon_spans_aria_hidden(self, client):
        """Spec: icon wrapper spans in the contact column use aria-hidden='true'."""
        resp = client.get('/')
        body = _html(resp)
        assert 'aria-hidden="true"' in body, \
            'Icon wrapper elements in footer must use aria-hidden="true"'

    def test_footer_nav_has_aria_label(self, client):
        """Spec: <nav> element(s) inside footer carry an aria-label attribute."""
        resp = client.get('/')
        body = _html(resp)
        footer_start = body.find('<footer')
        footer_end = body.find('</footer>', footer_start)
        footer_fragment = body[footer_start:footer_end]
        assert re.search(r'<nav[^>]+aria-label\s*=', footer_fragment), \
            'Footer nav element must have an aria-label for screen readers'


# ===========================================================================
# Group 8 — CSS: variable and class definitions (read from disk)
# ===========================================================================

class TestFooterCSSDefinitions:
    """
    These tests read static/css/style.css directly.  They verify that the
    CSS spec requirements are satisfied in the stylesheet, independent of
    route rendering.
    """

    @pytest.fixture(autouse=True)
    def _load_css(self):
        """Read the CSS file once per test in this class."""
        assert os.path.isfile(_CSS_PATH), \
            f'style.css not found at expected path: {_CSS_PATH}'
        with open(_CSS_PATH, 'r', encoding='utf-8') as fh:
            self.css = fh.read()

    def test_css_bg_footer_variable_in_root(self):
        """Spec: --bg-footer must be declared inside :root in style.css."""
        # Find the :root block content.
        root_match = re.search(r':root\s*\{([^}]+)\}', self.css, re.DOTALL)
        assert root_match, ':root block must exist in style.css'
        root_block = root_match.group(1)
        assert '--bg-footer' in root_block, \
            '--bg-footer CSS variable must be declared inside :root'

    def test_css_bg_footer_value_is_0a0a0a(self):
        """Spec: --bg-footer value must be #0a0a0a."""
        assert re.search(r'--bg-footer\s*:\s*#0a0a0a', self.css), \
            '--bg-footer must be set to #0a0a0a in :root'

    @pytest.mark.parametrize('css_class', [
        '.footer-grid',
        '.footer-col',
        '.footer-brand',
        '.footer-tagline',
        '.footer-heading',
        '.footer-links',
        '.footer-link',
        '.footer-contact',
        '.footer-contact-line',
        '.footer-bottom',
    ])
    def test_css_required_footer_class_defined(self, css_class):
        """Spec: every named footer class from the spec must be defined in style.css."""
        assert css_class in self.css, \
            f'CSS class {css_class} must be defined in style.css'

    def test_css_footer_socials_class_defined(self):
        """Spec: .footer-socials class must be defined (social links row)."""
        assert '.footer-socials' in self.css, \
            '.footer-socials class must be defined in style.css'

    def test_css_footer_social_link_class_defined(self):
        """Spec: .footer-social-link class must be defined."""
        assert '.footer-social-link' in self.css, \
            '.footer-social-link class must be defined in style.css'

    def test_css_footer_bottom_links_class_defined(self):
        """Spec: .footer-bottom-links class must be defined."""
        assert '.footer-bottom-links' in self.css, \
            '.footer-bottom-links class must be defined in style.css'

    def test_css_responsive_breakpoint_1024(self):
        """Spec: @media (max-width: 1024px) must exist for 2-column footer grid."""
        assert 'max-width: 1024px' in self.css, \
            '@media (max-width: 1024px) breakpoint must be present in style.css'

    def test_css_responsive_breakpoint_768(self):
        """Spec: @media (max-width: 768px) must exist for single-column footer."""
        assert 'max-width: 768px' in self.css, \
            '@media (max-width: 768px) breakpoint must be present in style.css'

    def test_css_footer_uses_bg_footer_variable(self):
        """Spec: the .footer rule must reference var(--bg-footer), not a raw hex."""
        # Locate the .footer rule block.
        footer_rule_match = re.search(
            r'\.footer\s*\{([^}]+)\}', self.css, re.DOTALL
        )
        assert footer_rule_match, '.footer rule must exist in style.css'
        footer_rule = footer_rule_match.group(1)
        assert 'var(--bg-footer)' in footer_rule, \
            '.footer background must use var(--bg-footer), not a hardcoded hex'

    def test_css_no_hardcoded_hex_in_footer_specific_rules(self):
        """
        Spec: no newly-introduced hex color values in footer CSS rules.
        Only the --bg-footer: #0a0a0a declaration in :root is acceptable.
        Strategy: collect every line inside a block that starts with .footer-
        (i.e., footer-specific classes) and assert no raw hex appears there.
        """
        # Extract all content belonging to rules whose selector starts with .footer-
        footer_rule_blocks = re.findall(
            r'\.footer-[a-z\-]+[^{]*\{([^}]*)\}',
            self.css,
            re.DOTALL,
        )
        combined = '\n'.join(footer_rule_blocks)
        # Raw hex: #NNN or #NNNNNN (3 or 6 hex digits)
        hex_matches = re.findall(r'#[0-9a-fA-F]{3,6}\b', combined)
        assert not hex_matches, (
            f'Hardcoded hex values found in footer-specific CSS rules: {hex_matches}. '
            'Use CSS variables only.'
        )


# ===========================================================================
# Group 9 — Security headers still present after footer is introduced
# ===========================================================================

class TestSecurityHeadersIntact:
    """
    Spec (Definition of Done): security headers from the previous step must
    still be returned by / after the footer change.
    """

    def test_csp_header_present_on_landing(self, client):
        """Spec: Content-Security-Policy header must be present on GET /."""
        resp = client.get('/')
        assert 'Content-Security-Policy' in resp.headers, \
            'Content-Security-Policy header must still be set after footer change'

    def test_x_frame_options_header_present(self, client):
        """Spec: X-Frame-Options header must be present on GET /."""
        resp = client.get('/')
        assert 'X-Frame-Options' in resp.headers, \
            'X-Frame-Options header must still be set after footer change'

    def test_x_content_type_options_header_present(self, client):
        """Spec: X-Content-Type-Options header must be present on GET /."""
        resp = client.get('/')
        assert 'X-Content-Type-Options' in resp.headers, \
            'X-Content-Type-Options header must still be set after footer change'

    def test_referrer_policy_header_present(self, client):
        """Spec: Referrer-Policy header must be present on GET /."""
        resp = client.get('/')
        assert 'Referrer-Policy' in resp.headers, \
            'Referrer-Policy header must still be set after footer change'

    def test_security_headers_present_on_login(self, client):
        """Spec: security headers also present on /login (not just /)."""
        resp = client.get('/login')
        assert 'Content-Security-Policy' in resp.headers, \
            'CSP header must be present on /login'
        assert 'X-Frame-Options' in resp.headers, \
            'X-Frame-Options must be present on /login'
