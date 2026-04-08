document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('logoutBtn')?.addEventListener('click', () => {
        // Перенаправляем на страницу входа
        window.location.href = '/accounts/logout/';
    });
});

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('accountBtn')?.addEventListener('click', () => {
        // Перенаправляем на страницу профиля
        window.location.href = '/accounts/about_me/';
    });
});