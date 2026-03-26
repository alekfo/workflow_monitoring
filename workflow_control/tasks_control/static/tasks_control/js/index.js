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

    // Функция для выполнения скриптов из загруженного HTML
    function executeScripts(html) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;

        const scripts = tempDiv.querySelectorAll('script');
        scripts.forEach(oldScript => {
            const newScript = document.createElement('script');

            // Копируем все атрибуты
            Array.from(oldScript.attributes).forEach(attr => {
                newScript.setAttribute(attr.name, attr.value);
            });

            // Копируем содержимое скрипта
            newScript.textContent = oldScript.textContent;

            // Удаляем старый скрипт
            oldScript.parentNode.removeChild(oldScript);

            // Добавляем новый скрипт в head или body
            document.head.appendChild(newScript);
        });

        // Возвращаем HTML без скриптов
        return tempDiv.innerHTML;
    }

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

            // Выполняем скрипты и получаем HTML без них
            const htmlWithoutScripts = executeScripts(html);

            // Вставляем HTML
            contentPanel.innerHTML = htmlWithoutScripts;

            // Вызываем функцию инициализации кнопок (если она существует)
            if (typeof window.initTasksToggle === 'function') {
                window.initTasksToggle();
            }

            // Также можно вызвать и другие функции инициализации
            if (typeof window.initStationTasks === 'function') {
                window.initStationTasks();
            }

        } catch (error) {
            contentPanel.innerHTML = `<p style="color: red;">Ошибка: ${error.message}</p>`;
        }
    }

    // Функция для перехода по URL
    function redirect_func(url) {
        window.location.href = url;
    }

    // Словарь соответствия data-section и URL
    const urlMap_for_contentPanel = {
        'tasks_all': '/tasks/bugs/',
        'tasks_mine': null,
        'objects_all': '/tasks/stations/',
        'warehouses_stock': null,
        'reports_download': null,
        'links_all': null,
        'charts_download': null,
        'alarms': null,
        'instructions': null,
        'others': null
    };

    const urlMap_for_redirect = {
        'tasks_seek': null,
        'tasks_add': '/tasks/bugs/create',
        'objects_seek': null,
        'objects_add': '/tasks/stations/create',
        'links_add': null,
        'charts_add': null,
    };

    // Обработка подкнопок
    const subButtons = document.querySelectorAll('.sub-button');
    subButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const section = btn.dataset.section;

            if (section in urlMap_for_contentPanel) {
                // Получаем URL из словаря и выводим в contentPanel
                const url = urlMap_for_contentPanel[section];
                if (!url) {
                    document.getElementById('content-panel').innerHTML = '<p>Раздел в разработке</p>';
                    return;
                }
                // Загружаем контент в contentPanel
                await loadContent(url);
            } else if (section in urlMap_for_redirect) {
                // Получаем URL из словаря и делаем редирект по URL
                const url = urlMap_for_redirect[section];
                if (!url) {
                    document.getElementById('content-panel').innerHTML = '<p>Раздел в разработке</p>';
                    return;
                }
                // Переходим по URL
                await redirect_func(url);
            }


        });
    });
});