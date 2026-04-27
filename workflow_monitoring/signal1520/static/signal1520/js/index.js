//if (!localStorage.getItem('access_token')) {
//    window.location.href = 'login.html';
//}

// код выполнится после полной загрузки HTML-документа
document.addEventListener('DOMContentLoaded', () => {

    // Словарь соответствия data-section и URL
    const urlMap_for_contentPanel = {
        'tasks_all': '/signal1520/bugs/',
        'tasks_mine': '/signal1520/bugs/my/',
        'objects_all': '/signal1520/stations/',
        'alarms': '/signal1520/alarms/',
        'warehouses_stock': null,
        'reports_download': null,
        'links_all': null,
        'charts_download': null,
        'instructions': '/signal1520/knowledge/',
        'others': null
    };

    const urlMap_for_redirect = {
        'tasks_seek': null,
        'tasks_add': '/signal1520/bugs/create',
        'objects_seek': null,
        'objects_add': '/signal1520/stations/create',
        'links_add': null,
        'charts_add': null,
        'instructions_add': '/signal1520/knowledge/create/',
    };

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

    // Функция для выполнения скриптов из контейнера (после вставки)
    function executeScripts(container) {
        const scripts = container.querySelectorAll('script');
        scripts.forEach(oldScript => {
            const newScript = document.createElement('script');
            Array.from(oldScript.attributes).forEach(attr => {
                newScript.setAttribute(attr.name, attr.value);
            });
            newScript.textContent = oldScript.textContent;
            oldScript.parentNode.removeChild(oldScript);
            document.head.appendChild(newScript);
        });
    }

    // Функция для загрузки контента по URL
    window.loadContentPanel = async function loadContent(url) {
        const contentPanel = document.getElementById('content-panel');
        contentPanel.innerHTML = '<p>Загрузка...</p>';
        try {
            const response = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) {
                if (response.status === 403) {
                    contentPanel.innerHTML = '<p>Нет прав. Обратитесь к разработчикам.</p>';
                    return;
                }
                throw new Error(`HTTP error ${response.status}`);
            }
            const html = await response.text();
            // Вставляем HTML целиком
            contentPanel.innerHTML = html;
            // Выполняем скрипты из вставленного HTML
            executeScripts(contentPanel);

            // Дополнительные инициализации
            if (typeof window.initTasksToggle === 'function') window.initTasksToggle();
            if (typeof window.initStationTasks === 'function') window.initStationTasks();
            if (typeof window.initBugFilter === 'function') window.initBugFilter();
            if (typeof window.initInstructions === 'function') window.initInstructions();
        } catch (error) {
            contentPanel.innerHTML = `<p style="color: red;">Ошибка: ${error.message}</p>`;
        }
    }

    // Функция для перехода по URL
    function redirect_func(url) {
        window.location.href = url;
    }

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
                await window.loadContentPanel(url);
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