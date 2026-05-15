window.initAlarmToggle = function () {
    if (document._alarmToggleInit) return;
    document._alarmToggleInit = true;

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.explanation-toggle');
        if (!btn) return;
        const cell = btn.closest('.explanation-cell');
        const short = cell.querySelector('.explanation-short');
        const full = cell.querySelector('.explanation-full');
        const expanded = full.style.display !== 'none';
        short.style.display = expanded ? 'inline' : 'none';
        full.style.display = expanded ? 'none' : 'inline';
        btn.textContent = expanded ? 'Развернуть' : 'Свернуть';
    });
};