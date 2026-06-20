/* theme.js — dark-mode toggle, mobile nav, and admin sidebar drawer.
   The no-FOUC pre-paint script in each <head> sets data-theme before this runs;
   here we just wire up the interactive controls. */
(function () {
    'use strict';

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        try { localStorage.setItem('theme', theme); } catch (e) { /* ignore */ }
        document.querySelectorAll('.theme-toggle').forEach(function (btn) {
            btn.textContent = theme === 'dark' ? '☀' : '☾'; // sun / moon
            btn.setAttribute('aria-label',
                theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
        });
    }

    function currentTheme() {
        return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    }

    document.addEventListener('DOMContentLoaded', function () {
        // Sync toggle icons with whatever the pre-paint script set.
        applyTheme(currentTheme());

        // Dark-mode toggles (storefront nav + admin sidebar).
        document.querySelectorAll('.theme-toggle').forEach(function (btn) {
            btn.addEventListener('click', function () {
                applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
            });
        });

        // Storefront hamburger nav.
        var navToggle = document.getElementById('nav-toggle');
        var navLinks = document.getElementById('nav-links');
        if (navToggle && navLinks) {
            navToggle.addEventListener('click', function () {
                var open = navLinks.classList.toggle('open');
                navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
        }

        // Admin sidebar drawer.
        var sidebar = document.getElementById('admin-sidebar');
        var sidebarToggle = document.getElementById('sidebar-toggle');
        var backdrop = document.getElementById('sidebar-backdrop');
        function closeSidebar() {
            if (!sidebar) return;
            sidebar.classList.remove('open');
            if (backdrop) backdrop.classList.remove('show');
        }
        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', function () {
                sidebar.classList.toggle('open');
                if (backdrop) backdrop.classList.toggle('show');
            });
        }
        if (backdrop) backdrop.addEventListener('click', closeSidebar);
    });
})();
