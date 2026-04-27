import os

from django.db import models
from django.contrib.auth.models import User


class Road(models.Model):
    title = models.CharField('Название', max_length=100)

    class Meta:
        verbose_name = 'Дорога/линия/район'
        verbose_name_plural = 'Дороги/линии/районы'
        ordering = ['title']

    def __str__(self):
        return self.title


class System(models.Model):
    title = models.CharField('Название', max_length=50)

    class Meta:
        verbose_name = 'Система'
        verbose_name_plural = 'Системы'
        ordering = ['title']

    def __str__(self):
        return self.title


class Station(models.Model):
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
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

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

    def __str__(self):
        return f"Задача #{self.id} на станции {self.station.name}"

class Comment(models.Model):
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
    title = models.CharField('Заголовок', max_length=200)
    description = models.TextField('Описание', blank=True)
    file = models.FileField(
        'Файл',
        upload_to=knowledge_file_path,
        blank=True,
        null=True
    )
    external_link = models.URLField('Ссылка на ресурс', blank=True)
    created_at = models.DateTimeField('Дата добавления', auto_now_add=True)
    updated_at = models.DateTimeField('Дата изменения', auto_now=True)

    class Meta:
        verbose_name = 'Материал базы знаний'
        verbose_name_plural = 'База знаний'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

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