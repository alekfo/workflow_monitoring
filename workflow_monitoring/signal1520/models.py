import os
from datetime import date, timedelta

from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('Slug', unique=True)

    class Meta:
        verbose_name = 'Организация'
        verbose_name_plural = 'Организации'

    def __str__(self):
        return self.name


class Road(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='roads',
        verbose_name='Организация',
        null=True,
        blank=True,
    )
    title = models.CharField('Название', max_length=100)

    class Meta:
        verbose_name = 'Дорога/линия/район'
        verbose_name_plural = 'Дороги/линии/районы'
        ordering = ['title']

    def __str__(self):
        return self.title


class System(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='systems',
        verbose_name='Организация',
        null=True,
        blank=True,
    )
    title = models.CharField('Название', max_length=50)

    class Meta:
        verbose_name = 'Система'
        verbose_name_plural = 'Системы'
        ordering = ['title']

    def __str__(self):
        return self.title


class Station(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='stations',
        verbose_name='Организация',
        null=True,
        blank=True,
    )
    name = models.CharField('Название станции/объекта', max_length=200)
    road = models.ForeignKey(
        Road,
        on_delete=models.PROTECT,
        related_name='stations',
        verbose_name='Дорога/линия/район',
    )
    description = models.TextField('Описание', blank=True)
    distance = models.CharField('Дистанция', max_length=20, blank=True, default='')
    system = models.ForeignKey(
        System,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stations',
        verbose_name='Система',
    )
    latitude = models.FloatField('Широта', null=True, blank=True)
    longitude = models.FloatField('Долгота', null=True, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    # SET_NULL: удаление пользователя не должно уносить станции организации вместе с задачами
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Станция'
        verbose_name_plural = 'Станции'
        ordering = ['road__title', 'name']

    def __str__(self):
        return f"{self.name} ({self.road})"

class Task(models.Model):
    #для создания перечислений (enums) для полей с фиксированным набором значений
    #каждый атрибут (NEW, IN_PROGRESS и т.д.) — это элемент перечисления.
    class Status(models.TextChoices):
        #Значение, которое сохраняется в базе данных — это первый элемент кортежа: 'new'
        #Второй элемент кортежа — человекочитаемое название, которое будет отображаться в формах, админке, выпадающих списках
        NEW = 'new', 'Новая'
        IN_PROGRESS = 'in_progress', 'В работе'
        COMPLETED = 'completed', 'Выполнена'
        CANCELLED = 'cancelled', 'Отменена'

    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='Станция'
    )
    description = models.TextField('Описание задачи')
    #choices=Status.choices — передаёт в поле все варианты для выбора.
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.NEW
    )
    responsible_organization = models.CharField(
        'Ответственная организация',
        max_length=200,
        blank=True
    )
    # Ответственный исполнитель — ссылка на пользователя (можно на EmployeeProfile, если есть)
    responsible_user = models.ForeignKey(
        User,  # или EmployeeProfile
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks',
        verbose_name='Ответственный исполнитель'
    )
    due_date = models.DateField('Срок выполнения', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    #auto_now=True — каждый раз, когда объект сохраняется (и при создании, и при изменении),
    # Django автоматически устанавливает этому полю текущую дату и время при изменении
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['-created_at']

    @property
    def row_color_class(self):
        if self.status == self.Status.COMPLETED:
            return 'row-completed'
        if self.due_date:
            today = date.today()
            if self.due_date < today:
                return 'row-overdue'
            if (self.due_date - today).days < 30:
                return 'row-due-soon'
        return ''

    @property
    def is_closed(self):
        return self.status in (self.Status.COMPLETED, self.Status.CANCELLED)

    def can_be_managed_by(self, user):
        """Править задачу и менять её статус могут суперпользователь, обладатель change_task и ответственный"""
        return (user.is_superuser
                or user.has_perm('signal1520.change_task')
                or (self.responsible_user_id is not None and self.responsible_user_id == user.pk))

    def allowed_statuses(self, user):
        """Статусы, в которые пользователь может перевести задачу. В «Новая» вернуть нельзя никому,
        закрытую задачу переоткрывает только суперпользователь."""
        if self.is_closed:
            return [self.Status.IN_PROGRESS] if user.is_superuser else []
        if not self.can_be_managed_by(user):
            return []
        if self.status == self.Status.NEW:
            return [self.Status.IN_PROGRESS, self.Status.COMPLETED, self.Status.CANCELLED]
        return [self.Status.COMPLETED, self.Status.CANCELLED]

    def change_status(self, new_status, user):
        """Меняет статус и записывает переход в историю. Права и допустимость перехода проверяет вызывающий код."""
        old_status = self.status
        with transaction.atomic():
            self.status = new_status
            self.save(update_fields=['status', 'updated_at'])
            change = TaskStatusChange.objects.create(
                task=self, from_status=old_status, to_status=new_status, changed_by=user,
            )
            ActivityEvent.log(ActivityEvent.Kind.TASK_STATUS, user, task=self)
            return change

    @property
    def last_status_change(self):
        return self.status_changes.first()

    def __str__(self):
        return f"Задача #{self.id} на станции {self.station.name}"


class TaskStatusChange(models.Model):
    """Запись о переводе задачи из одного статуса в другой: кто и когда."""
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='status_changes',
        verbose_name='Задача'
    )
    from_status = models.CharField('Из статуса', max_length=20, choices=Task.Status.choices)
    to_status = models.CharField('В статус', max_length=20, choices=Task.Status.choices)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_status_changes',
        verbose_name='Кто изменил'
    )
    changed_at = models.DateTimeField('Когда изменён', auto_now_add=True)

    class Meta:
        verbose_name = 'Смена статуса задачи'
        verbose_name_plural = 'Смены статусов задач'
        ordering = ['-changed_at', '-pk']
        # своих прав у истории нет: в админке их путают с «Can change Задача», а на смену статуса они не влияют
        default_permissions = ()

    def author_name(self):
        """Возвращает отображаемое имя того, кто сменил статус"""
        user = self.changed_by
        if not user:
            return "Удалённый пользователь"
        return user.get_full_name() or user.username

    def __str__(self):
        return f"Задача #{self.task_id}: {self.get_from_status_display()} → {self.get_to_status_display()}"


class ActivityEvent(models.Model):
    """Запись ленты «Последние изменения» на главной. Текст хранится готовой строкой и переживает удаление объекта."""

    class Kind(models.TextChoices):
        TASK_CREATED = 'task_created', 'Задача создана'
        TASK_STATUS = 'task_status', 'Статус задачи изменён'
        TASK_COMMENT = 'task_comment', 'Комментарий к задаче'
        TASK_ATTACHMENT = 'task_attachment', 'Вложение к задаче'
        STATION_CREATED = 'station_created', 'Объект создан'

    # события по задачам видит обладатель view_task, по объектам — view_station
    TASK_KINDS = (Kind.TASK_CREATED, Kind.TASK_STATUS, Kind.TASK_COMMENT, Kind.TASK_ATTACHMENT)
    STATION_KINDS = (Kind.STATION_CREATED,)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='activity_events',
        verbose_name='Организация'
    )
    kind = models.CharField('Событие', max_length=20, choices=Kind.choices)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_events',
        verbose_name='Кто'
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_events',
        verbose_name='Задача'
    )
    station = models.ForeignKey(
        Station,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_events',
        verbose_name='Объект'
    )
    text = models.CharField('Текст', max_length=300)
    # не auto_now_add: миграция 0019 заполняет ленту прошлыми событиями с их настоящим временем
    created_at = models.DateTimeField('Когда', default=timezone.now)

    class Meta:
        verbose_name = 'Событие ленты'
        verbose_name_plural = 'События ленты'
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['organization', '-created_at'], name='activity_org_created_idx')]
        default_permissions = ()

    @staticmethod
    def build_text(kind, task=None, station=None):
        """Строка события. Миграция 0019 собирает такие же строки для прошлых событий."""
        if kind == ActivityEvent.Kind.STATION_CREATED:
            return f'Объект «{station.name}» — создан'
        action = {
            ActivityEvent.Kind.TASK_CREATED: 'создана',
            ActivityEvent.Kind.TASK_STATUS: f'статус «{task.get_status_display()}»',
            ActivityEvent.Kind.TASK_COMMENT: 'добавлен комментарий',
            ActivityEvent.Kind.TASK_ATTACHMENT: 'добавлено вложение',
        }[kind]
        return f'Задача #{task.pk}, {task.station.name} — {action}'

    @classmethod
    def log(cls, kind, user, task=None, station=None):
        """Записывает событие. Для события по задаче объект берётся из самой задачи."""
        station = station or task.station
        return cls.objects.create(
            organization=station.organization,
            kind=kind,
            user=user,
            task=task,
            station=station,
            text=cls.build_text(kind, task=task, station=station)[:300],
        )

    def text_parts(self):
        """Текст события двумя частями для ленты: о чём («Задача #25, Бутырская») и что произошло («создана»)"""
        subject, sep, action = self.text.rpartition(' — ')
        return (subject, action) if sep else (self.text, '')

    def author_name(self):
        """Имя автора; пустая строка, если автор неизвестен (прошлые события) или удалён"""
        user = self.user
        if not user:
            return ''
        return user.get_full_name() or user.username

    def __str__(self):
        return self.text

class Comment(models.Model):
    EDIT_WINDOW = timedelta(hours=24)

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Задача'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comments',
        verbose_name='Автор комментария'
    )
    body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField('Дата изменения', auto_now=True)

    def author_name(self):
        """Возвращает отображаемое имя автора комментария"""
        user = self.user
        if not user:
            return "Аноним"
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        if user.first_name:
            return user.first_name
        return user.username

    def can_be_edited_by(self, user):
        """Править комментарий может только автор и только в течение EDIT_WINDOW после создания"""
        if self.user_id is None or self.user_id != user.pk:
            return False
        return timezone.now() - self.created_at < self.EDIT_WINDOW

    @property
    def is_edited(self):
        # created_at и updated_at при создании ставятся порознь и расходятся на доли секунды
        return self.updated_at - self.created_at > timedelta(seconds=1)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']

def task_attachment_path(instance, filename):
    # путь для сохранения файлов: tasks/task_<id>/<filename>
    return f'tasks/task_{instance.task.id}/{filename}'

class Attachment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Задача'
    )
    #Параметр upload_to определяет путь, по которому будет сохранён загруженный файл относительно корневой папки,
    # указанной в MEDIA_ROOT в настройках (settings.py).
    file = models.FileField(
        'Файл',
        upload_to=task_attachment_path
    )

    #
    # При сохранении объекта (например, через форму или прямо в коде) происходит следующее:
    #
    # - Django получает загруженный файл.
    #
    # - Вызывается функция upload_to с instance и исходным именем файла.
    #
    # - Файл сохраняется в MEDIA_ROOT/tasks/task_5/myfile.pdf.
    #
    # - В поле file модели Attachment записывается относительный путь tasks/task_5/myfile.pdf.
    #

    description = models.CharField('Описание', max_length=255, blank=True)
    uploaded_at = models.DateTimeField('Дата загрузки', auto_now_add=True)

    class Meta:
        verbose_name = 'Вложение'
        verbose_name_plural = 'Вложения'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Вложение к задаче {self.task.id}: {self.file.name}"

    def is_image(self):
        """Возвращает True, если файл является изображением"""
        ext = os.path.splitext(self.file.name)[1].lower()
        return ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')

    def filename(self):
        """Возвращает чистое имя файла (без пути)"""
        return os.path.basename(self.file.name)


class AlarmInfo(models.Model):
    number = models.CharField(
        'Номер аларма',
        max_length=5,
        primary_key=True
    )
    description = models.CharField(
        'Описание',
        max_length=600
    )
    explanation = models.TextField(
        'Пояснение',
        max_length=1000
    )

    class Meta:
        verbose_name = 'Аларм'
        verbose_name_plural = 'Алармы'
        ordering = ['number']

    def __str__(self):
        return self.number

def knowledge_file_path(instance, filename):
    return f'knowledge/{filename}'

class Knowledge(models.Model):
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_knowledge',
        verbose_name='Добавил',
    )
    file = models.FileField('Файл', upload_to=knowledge_file_path, blank=True, null=True)
    external_link = models.URLField('Ссылка на ресурс', blank=True)
    created_at = models.DateTimeField('Дата добавления', auto_now_add=True)

    class Meta:
        verbose_name = 'Файл/ссылка базы знаний'
        verbose_name_plural = 'Файлы/ссылки базы знаний'
        ordering = ['-created_at']

    def __str__(self):
        return self.filename() or self.external_link or f'#{self.pk}'

    def filename(self):
        return os.path.basename(self.file.name) if self.file else ''


class UserKnowledge(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_knowledge',
        verbose_name='Пользователь',
    )
    knowledge = models.ForeignKey(
        Knowledge,
        on_delete=models.CASCADE,
        related_name='user_knowledge',
        verbose_name='Материал',
    )
    title = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    created_at = models.DateTimeField('Дата добавления', auto_now_add=True)

    class Meta:
        verbose_name = 'Инструкция пользователя'
        verbose_name_plural = 'Инструкции пользователей'
        ordering = ['-created_at']
        unique_together = [('user', 'knowledge')]

    def __str__(self):
        return f'{self.user.username}: {self.title}'

class EquipmentType(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='equipment_types',
        verbose_name='Организация',
    )
    title = models.CharField('Тип оборудования', max_length=100)

    class Meta:
        verbose_name = 'Тип оборудования'
        verbose_name_plural = 'Типы оборудования'
        ordering = ['title']

    def __str__(self):
        return self.title


class Warehouse(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='warehouses',
        verbose_name='Организация',
    )
    title = models.CharField('Название', max_length=200)
    responsible_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='warehouses',
        verbose_name='Ответственный',
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Склад'
        verbose_name_plural = 'Склады'
        ordering = ['title']

    def __str__(self):
        return self.title


class Equipment(models.Model):
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='equipment',
        verbose_name='Склад',
    )
    station = models.ForeignKey(
        Station,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment',
        verbose_name='Объект/станция',
    )
    type = models.ForeignKey(
        EquipmentType,
        on_delete=models.PROTECT,
        related_name='equipment',
        verbose_name='Тип оборудования',
    )
    factory_number = models.CharField('Заводской номер', max_length=100, blank=True, default='')
    manufacturer = models.CharField('Изготовитель', max_length=200, blank=True, default='')
    date_of_manufacture = models.DateField('Дата изготовления', null=True, blank=True)
    added_at = models.DateTimeField('Дата добавления', auto_now_add=True)

    class Meta:
        verbose_name = 'Оборудование'
        verbose_name_plural = 'Оборудование'
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.type} → {self.warehouse}"


class Link(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='links',
        verbose_name='Пользователь'
    )
    title = models.CharField('Название', max_length=200)
    url = models.URLField('Ссылка')
    description = models.TextField('Описание', blank=True)
    created_at = models.DateTimeField('Дата добавления', auto_now_add=True)

    class Meta:
        verbose_name = 'Ссылка'
        verbose_name_plural = 'Ссылки'
        ordering = ['-created_at']

    def __str__(self):
        return self.title