document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('logoutBtn')?.addEventListener('click', () => {
        // Перенаправляем на страницу входа
        window.location.href = '/accounts/logout/';
    });
});

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('accountBtn')?.addEventListener('click', () => {
        window.location.href = '/accounts/about_me/';
    });
});

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('contactBtn')?.addEventListener('click', () => {
        window.location.href = '/' + (window.ORG_SLUG || 'signal1520') + '/contact/';
    });
});