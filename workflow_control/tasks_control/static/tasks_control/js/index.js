//if (!localStorage.getItem('access_token')) {
//    window.location.href = 'login.html';
//}

// код выполнится после полной загрузки HTML-документа
document.addEventListener('DOMContentLoaded', () => {
    // ---------- Аккордеон для главных кнопок ----------
    const mainButtons = document.querySelectorAll('.main-btn');

    mainButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const menuItem = btn.closest('.menu-item');
            const submenu = menuItem.querySelector('.submenu');

            // Закрываем все другие открытые подменю (аккордеон)
            document.querySelectorAll('.submenu.show').forEach(openSub => {
                if (openSub !== submenu) {
                    openSub.classList.remove('show');
                    const parentItem = openSub.closest('.menu-item');
                    if (parentItem) {
                        parentItem.querySelector('.main-btn').classList.remove('active');
                    }
                }
            });

            // Переключаем текущее подменю
            submenu.classList.toggle('show');
            btn.classList.toggle('active', submenu.classList.contains('show'));
        });
    });

    // Функция для загрузки контента по URL
    async function loadContent(url) {
        const contentPanel = document.getElementById('content-panel');

        // Показываем загрузку
        contentPanel.innerHTML = '<p>Загрузка...</p>';

        try {
            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }

            const html = await response.text();
            contentPanel.innerHTML = html;

        } catch (error) {
            contentPanel.innerHTML = `<p style="color: red;">Ошибка: ${error.message}</p>`;
        }
    }

    // Словарь соответствия data-section и URL
    const urlMap = {
        'tasks_all': null,
        'tasks_mine': null,
        'tasks_seek': null,
        'tasks_add': null,
        'objects_all': '/tasks/stations/',
        'objects_seek': null,
        'objects_add': null,
        'warehouses_stock': null,
        'reports_download': null,
        'links_all': null,
        'links_add': null,
        'charts_download': null,
        'charts_add': null,
        'alarms': null,
        'instructions': null,
        'others': null
    };

    // Обработка подкнопок
    const subButtons = document.querySelectorAll('.sub-button');
    subButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const section = btn.dataset.section;

            // Получаем URL из словаря
            const url = urlMap[section];

            if (!url) {
                document.getElementById('content-panel').innerHTML = '<p>Раздел в разработке</p>';
                return;
            }

            // Загружаем контент
            await loadContent(url);
        });
    });
});