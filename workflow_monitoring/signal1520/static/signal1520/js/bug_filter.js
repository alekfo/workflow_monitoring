// bug_filter.js
window.initBugFilter = function () {
    const searchForm = document.getElementById('search-form');
    if (!searchForm || searchForm.dataset.filterInitialized) return;
    searchForm.dataset.filterInitialized = 'true';

    const baseUrl = searchForm.getAttribute('data-base-url');

    function getContainer(doc) {
        return doc.querySelector('.table-and-pagination') || doc.querySelector('.table-wrapper');
    }

    function replaceContainer(newDoc) {
        const newContainer = getContainer(newDoc);
        const contentPanel = document.getElementById('content-panel');
        const root = contentPanel || document;
        const currentContainer = root.querySelector('.table-and-pagination') || root.querySelector('.table-wrapper');
        if (newContainer && currentContainer) {
            currentContainer.outerHTML = newContainer.outerHTML;
        }
    }

    searchForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const searchInput = this.querySelector('input[name="search"]');
        const searchValue = searchInput.value;
        const url = baseUrl + '?search=' + encodeURIComponent(searchValue);
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(response => response.text())
            .then(html => {
                const doc = new DOMParser().parseFromString(html, 'text/html');
                replaceContainer(doc);
                history.replaceState(null, '', url);
                const resetLink = document.getElementById('reset-search');
                if (resetLink) {
                    resetLink.style.display = searchValue ? 'inline-block' : 'none';
                }
            })
            .catch(error => console.error('Ошибка поиска:', error));
    });

    const resetLink = document.getElementById('reset-search');
    if (resetLink) {
        resetLink.addEventListener('click', function (e) {
            e.preventDefault();
            fetch(baseUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(response => response.text())
                .then(html => {
                    const doc = new DOMParser().parseFromString(html, 'text/html');
                    replaceContainer(doc);
                    history.replaceState(null, '', baseUrl);
                    const searchInput = document.querySelector('input[name="search"]');
                    if (searchInput) searchInput.value = '';
                    resetLink.style.display = 'none';
                })
                .catch(error => console.error('Ошибка сброса:', error));
        });
    }

    // Перехват кликов по ссылкам пагинации
    const contentPanel = document.getElementById('content-panel');
    const root = contentPanel || document;
    const paginationContainer = root.querySelector('.pagination');
    if (paginationContainer) {
        paginationContainer.addEventListener('click', function (e) {
            const link = e.target.closest('a');
            if (!link) return;
            e.preventDefault();
            const url = baseUrl + link.getAttribute('href');
            if (typeof window.loadContentPanel === 'function') {
                window.loadContentPanel(url);
            }
        });
    }
};
