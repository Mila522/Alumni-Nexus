const panelTitles = {
        'section-overview':             'Overview',
        'section-users':                'Registered Users',
        'section-mentor-applications':  'Mentor Applications',
        'section-active-mentors':       'Active Mentors',
        'section-mentorship-requests':  'Mentorship Requests',
        'section-posts':                'Posts',
        'section-events':               'Events / RSVP'
    };

    function activatePanel(targetId) {
        document.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('active'));
        const target = document.getElementById(targetId);
        if (target) target.classList.add('active');

        document.querySelectorAll('.dashboard-nav .nav-link').forEach(link => {
            link.classList.remove('active');
            if (link.dataset.target === targetId) link.classList.add('active');
        });

        const titleEl = document.getElementById('topbar-title');
        if (titleEl && panelTitles[targetId]) titleEl.textContent = panelTitles[targetId];

        history.replaceState(null, '', '#' + targetId);
    }

    document.querySelectorAll('.nav-link[data-target]').forEach(link => {
        link.addEventListener('click', e => { e.preventDefault(); activatePanel(link.dataset.target); });
    });

    document.querySelectorAll('.nav-link-inline[data-target]').forEach(link => {
        link.addEventListener('click', e => { e.preventDefault(); activatePanel(link.dataset.target); });
    });

    window.addEventListener('DOMContentLoaded', () => {
        const hash = window.location.hash.replace('#', '');
        if (hash && document.getElementById(hash)) activatePanel(hash);
    });
