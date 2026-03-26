// stations.js
// Функциональность раскрытия списка задач
window.initTasksToggle = function() {
    const toggleButtons = document.querySelectorAll('.tasks-toggle-btn');

    console.log('Инициализация кнопок, найдено:', toggleButtons.length); // Для отладки

    toggleButtons.forEach(button => {
        // Проверяем, не инициализирована ли уже кнопка
        if (button.hasAttribute('data-initialized')) {
            return;
        }

        const stationId = button.getAttribute('data-station-id');
        const tasksList = document.getElementById(`tasks-${stationId}`);
        const icon = button.querySelector('.toggle-icon');

        if (tasksList) {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();

                console.log('Клик по кнопке, ID станции:', stationId); // Для отладки

                if (tasksList.style.display === 'none' || getComputedStyle(tasksList).display === 'none') {
                    tasksList.style.display = 'block';
                    if (icon) icon.textContent = '▼';
                    this.classList.add('expanded');
                } else {
                    tasksList.style.display = 'none';
                    if (icon) icon.textContent = '▶';
                    this.classList.remove('expanded');
                }
            });

            // Отмечаем кнопку как инициализированную
            button.setAttribute('data-initialized', 'true');
        }
    });
};

// Автоматическая инициализация при загрузке страницы
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.initTasksToggle);
} else {
    window.initTasksToggle();
}