// sidebar.js
// Компьютер: клик по значку раскрывает вправо ряд кнопок-разделов поверх страницы,
// клик мимо или Escape возвращает меню в исходное состояние (только значки).
// Телефон (см. @media в styles.css): панель скрыта, бургер в шапке открывает её списком.
document.addEventListener('DOMContentLoaded', () => {
    const rail = document.getElementById('side-rail');
    if (!rail) return;

    const toggles = rail.querySelectorAll('.rail-btn[aria-controls]');
    const burger = document.getElementById('nav-toggle');

    function setOpen(btn, open) {
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        document.getElementById(btn.getAttribute('aria-controls')).classList.toggle('is-open', open);
    }

    function closeAll(except) {
        toggles.forEach(btn => {
            if (btn !== except) setOpen(btn, false);
        });
    }

    function setMenuOpen(open) {
        rail.classList.toggle('is-open', open);
        if (burger) burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    toggles.forEach(btn => {
        btn.addEventListener('click', () => {
            closeAll(btn);
            setOpen(btn, btn.getAttribute('aria-expanded') !== 'true');
        });
    });

    if (burger) {
        burger.addEventListener('click', () => {
            setMenuOpen(!rail.classList.contains('is-open'));
        });
    }

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.rail-group')) closeAll();
        if (!e.target.closest('#side-rail, #nav-toggle')) setMenuOpen(false);
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeAll();
            setMenuOpen(false);
        }
    });
});
