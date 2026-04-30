window.validateForm = function(formId, rules) {
    const form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener('submit', function(e) {
        form.querySelectorAll('.js-validation-error').forEach(el => el.remove());
        form.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));

        let valid = true;

        rules.forEach(function(rule) {
            const field = document.getElementById(rule.id);
            if (!field) return;

            const empty = field.tagName === 'SELECT'
                ? field.value === ''
                : field.value.trim() === '';

            if (rule.required && empty) {
                valid = false;
                field.classList.add('input-error');
                const group = field.closest('.form-group');
                if (group) {
                    const span = document.createElement('span');
                    span.className = 'error-message js-validation-error';
                    span.textContent = rule.message || 'Обязательное поле';
                    group.appendChild(span);
                }
            }
        });

        if (!valid) e.preventDefault();
    });
};
