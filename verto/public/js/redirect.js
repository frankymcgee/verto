document.addEventListener('DOMContentLoaded', function () {
    if (window.location.pathname === '/raven_mobile/direct-messages') {
        window.location.replace('/raven');
    }
    if (window.location.pathname === '/raven_mobile/channels') {
        window.location.replace('/raven');
    }
});