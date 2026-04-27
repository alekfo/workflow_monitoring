window.initInstructions = function () {
    document.querySelectorAll('.btn-delete[data-url]').forEach(function (btn) {
        if (btn.dataset.initialized) return;
        btn.dataset.initialized = 'true';

        btn.addEventListener('click', async function () {
            const row = btn.closest('[data-row-pk]');
            const title = row?.querySelector('.link-title, strong')?.textContent?.trim() || 'запись';
            if (!confirm('Удалить «' + title + '»?')) return;

            const url = btn.dataset.url;
            const pk = btn.dataset.pk;
            const csrfToken = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken },
                });
                if (response.ok) {
                    document.querySelectorAll('[data-row-pk="' + pk + '"]').forEach(el => el.remove());
                } else {
                    alert('Не удалось удалить запись.');
                }
            } catch {
                alert('Ошибка сети при удалении.');
            }
        });
    });
};
