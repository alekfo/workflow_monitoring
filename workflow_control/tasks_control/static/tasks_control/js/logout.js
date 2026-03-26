document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('logoutBtn')?.addEventListener('click', () => {
        // Перенаправляем на страницу входа
        window.location.href = '/accounts/logout/';
    });
});