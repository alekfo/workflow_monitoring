import io
import json
import logging

import openpyxl
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.models import Group, User
from django.views import View
from django.db import models
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin

from django.conf import settings
from django.core.mail import send_mail

from .models import Station, Task, Comment, Attachment, AlarmInfo, Road, System, Knowledge, UserKnowledge, Warehouse, Equipment, EquipmentType
from .forms import KnowledgeForm, ContactForm
from .mixins import OrgMixin

logger = logging.getLogger('signal1520')

class TasksIndexView(OrgMixin, LoginRequiredMixin, View):
    """Главная страница приложения."""

    def get(self, request: HttpRequest, org_slug: str) -> HttpResponse:
        return render(request, 'signal1520/index.html')

class StationListView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Список всех объектов (станций). Доступен суперпользователям и пользователям с правом view_station."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.view_station'):
            return True
        return False

    model = Station
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('road', 'system').prefetch_related('tasks').order_by('-pk')
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                models.Q(name__icontains=search_query) |
                models.Q(road__title__icontains=search_query) |
                models.Q(distance__icontains=search_query) |
                models.Q(system__title__icontains=search_query)
            )
        return queryset

class StationDetailView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Детальная страница объекта (станции) с привязанными задачами."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.view_station'):
            return True
        return False

    template_name = 'signal1520/station_details.html'
    queryset = Station.objects.select_related('road', 'system').prefetch_related("tasks")
    context_object_name = "station"  # имя, доступное в шаблоне

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     # Проверяем, может ли пользователь редактировать станцию
    #     user = self.request.user
    #     station = self.get_object()
    #
    #     can_edit = (
    #             user.is_superuser or
    #             user.has_perm('signal1520.change_station') or
    #             station.created_by == user
    #     )
    #     context['can_edit_station'] = can_edit
    #     return context

class StationCreateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Форма создания нового объекта (станции). Доступна суперпользователям и пользователям с правом add_station."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.add_station'):
            return True
        return False

    model = Station
    fields = "name", "road", "distance", "system", "description", "latitude", "longitude"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        org = self.get_org()
        form.fields['road'].queryset = Road.objects.filter(organization=org)
        form.fields['system'].queryset = System.objects.filter(organization=org)
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.organization = self.get_org()
        response = super().form_valid(form)
        logger.info('Станция создана: "%s" pk=%s (org=%s, user=%s)',
                    self.object.name, self.object.pk, self.get_org().slug, self.request.user.username)
        return response

    def get_success_url(self):
        return reverse("signal1520:station_details", kwargs=self.org_kwargs(pk=self.object.pk))

    def handle_no_permission(self):
        logger.warning('Отказ в доступе к созданию станции (user=%s)', self.request.user.username)
        return redirect(reverse('authentication:error'))


class StationCheckNameView(OrgMixin, LoginRequiredMixin, View):
    """AJAX: возвращает список станций организации с похожим названием."""

    def get(self, request, *args, **kwargs):
        name = request.GET.get('name', '').strip()
        if not name:
            return JsonResponse({'stations': []})
        org = self.get_org()
        qs = Station.objects.filter(organization=org, name__icontains=name)
        exclude_pk = request.GET.get('exclude')
        if exclude_pk and exclude_pk.isdigit():
            qs = qs.exclude(pk=int(exclude_pk))
        qs = qs.select_related('road').values('id', 'name', 'road__title')[:10]
        return JsonResponse({'stations': list(qs)})


class StationUpdateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Форма редактирования существующего объекта (станции)."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.change_station'):
            return True
        return False

    model = Station
    fields = "name", "road", "distance", "system", "description", "latitude", "longitude"
    template_name = 'signal1520/station_update_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        org = self.get_org()
        form.fields['road'].queryset = Road.objects.filter(organization=org)
        form.fields['system'].queryset = System.objects.filter(organization=org)
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info('Станция обновлена: "%s" pk=%s (org=%s, user=%s)',
                    self.object.name, self.object.pk, self.get_org().slug, self.request.user.username)
        return response

    def get_success_url(self):
        return reverse("signal1520:station_details", kwargs=self.org_kwargs(pk=self.object.pk))


class BugsListView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):

    """Список всех задач с поиском по описанию, станции, организации и статусу."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.view_task'):
            return True
        return False

    model = Task
    template_name = 'signal1520/bug_list.html'
    paginate_by = 10
    org_filter_field = 'station__organization'

    def get_queryset(self):
        queryset = super().get_queryset().select_related("responsible_user", "station")
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                models.Q(description__icontains=search_query) |
                models.Q(station__name__icontains=search_query) |
                models.Q(responsible_organization__icontains=search_query) |
                models.Q(status__icontains=search_query)
            )
        return queryset

class MyBugsListView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Список задач, назначенных на текущего пользователя, с поддержкой поиска."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.view_task'):
            return True
        return False

    model = Task
    template_name = 'signal1520/my_bug_list.html'
    paginate_by = 10
    org_filter_field = 'station__organization'

    def get_queryset(self):
        queryset = super().get_queryset().filter(responsible_user=self.request.user).select_related("responsible_user", "station")
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                models.Q(description__icontains=search_query) |
                models.Q(station__name__icontains=search_query) |
                models.Q(responsible_organization__icontains=search_query) |
                models.Q(status__icontains=search_query)
            )
        return queryset

class BugDetailView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Детальная страница задачи.

    GET  — отображает задачу с комментариями и вложениями.
    POST — обрабатывает три сценария:
           1. Загрузка файла-вложения.
           2. Добавление текстового комментария.
           3. Изменение статуса задачи (JSON-запрос от JavaScript).
    """

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.view_task'):
            return True
        return False

    template_name = 'signal1520/bug_details.html'
    queryset = Task.objects.select_related("responsible_user", "station").prefetch_related("comments", "attachments")
    context_object_name = "bug"
    org_filter_field = 'station__organization'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # 1. --- Обработка вложения ---
        if 'file' in request.FILES:
            attachment = Attachment(
                task=self.object,
                file=request.FILES['file'],
                description=request.POST.get('description', '')
            )
            attachment.save()
            logger.info('Вложение добавлено к задаче pk=%s (user=%s)', self.object.pk, request.user.username)
            return redirect(reverse('signal1520:bug_details', kwargs=self.org_kwargs(pk=self.object.pk)))

        # 2. Обработка добавления комментария (обычная форма)
        if 'comment_text' in request.POST:
            comment_text = request.POST.get('comment_text', '').strip()
            if comment_text:
                Comment.objects.create(
                    task=self.object,
                    user=request.user,
                    body=comment_text
                )
                logger.info('Комментарий добавлен к задаче pk=%s (user=%s)', self.object.pk, request.user.username)
            return redirect(reverse('signal1520:bug_details', kwargs=self.org_kwargs(pk=self.object.pk)))

        # 3. Обработка изменения статуса (JSON-запрос от JavaScript)
        # Проверка прав на изменение статуса
        if not (request.user.is_superuser or
                request.user.has_perm('signal1520.change_task') or
                self.object.responsible_user == request.user):
            return JsonResponse({'error': 'Недостаточно прав'}, status=403)

        try:
            data = json.loads(request.body)
            new_status = data.get('status')
        except:
            return JsonResponse({'error': 'Неверные данные'}, status=400)

        valid_statuses = [choice[0] for choice in Task.Status.choices]
        if new_status not in valid_statuses:
            return JsonResponse({'error': 'Недопустимый статус'}, status=400)

        self.object.status = new_status
        self.object.save()
        logger.info('Статус задачи pk=%s изменён на "%s" (user=%s)',
                    self.object.pk, new_status, request.user.username)
        return JsonResponse({
            'success': True,
            'status': new_status,
            'status_display': self.object.get_status_display()
        })

class BugCreateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Форма создания новой задачи. Ответственный сотрудник устанавливается автоматически как текущий пользователь."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.add_task'):
            return True
        return False

    model = Task
    template_name = 'signal1520/bug_form.html'
    fields = "station", "description", "responsible_organization", "due_date"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['station'].queryset = Station.objects.filter(organization=self.get_org())
        return form

    def form_valid(self, form):
        form.instance.responsible_user = self.request.user
        response = super().form_valid(form)
        logger.info('Задача создана: pk=%s, станция="%s" (org=%s, user=%s)',
                    self.object.pk, self.object.station, self.get_org().slug, self.request.user.username)
        return response

    def get_success_url(self):
        return reverse("signal1520:bug_details", kwargs=self.org_kwargs(pk=self.object.pk))

    def handle_no_permission(self):
        logger.warning('Отказ в доступе к созданию задачи (user=%s)', self.request.user.username)
        return redirect(reverse('authentication:error'))

class BugUpdateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Форма редактирования задачи. Доступна суперпользователям, пользователям с правом change_task и ответственному сотруднику."""

    def test_func(self):
        bug = self.get_object()
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.change_task'):
            return True
        if bug.responsible_user == self.request.user:
            return True
        return False

    model = Task
    fields = "station", "description", "status", "responsible_organization", "due_date"
    template_name = 'signal1520/bug_update_form.html'
    org_filter_field = 'station__organization'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['station'].queryset = Station.objects.filter(organization=self.get_org())
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info('Задача обновлена: pk=%s (org=%s, user=%s)',
                    self.object.pk, self.get_org().slug, self.request.user.username)
        return response

    def get_success_url(self):
        return reverse("signal1520:bug_details", kwargs=self.org_kwargs(pk=self.object.pk))

class AlarmListView(OrgMixin, LoginRequiredMixin, ListView):
    """Список сигнальных событий (тревог) с поиском по номеру. Пагинация по 20 записей."""

    model = AlarmInfo
    template_name = 'signal1520/alarm_list.html'
    context_object_name = 'alarms'
    paginate_by = 10

    def get_queryset(self):
        # AlarmInfo — глобальный справочник, org-фильтрация не применяется
        queryset = AlarmInfo.objects.all()
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(number__icontains=search_query)
        return queryset


class StationsExportView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, View):
    """Выгрузка списка станций в .xlsx."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_station')

    def get(self, request, **kwargs):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Станции'

        headers = ['ID', 'Наименование', 'Дорога/линия/район', 'Дистанция', 'Система', 'Описание', 'Широта', 'Долгота', 'Дата создания', 'Создал']
        ws.append(headers)

        for station in Station.objects.filter(organization=self.get_org()).select_related('created_by', 'road', 'system').order_by('pk'):
            ws.append([
                station.pk,
                station.name,
                station.road.title if station.road else '',
                station.distance,
                station.system.title if station.system else '',
                station.description,
                station.latitude,
                station.longitude,
                station.created_at.strftime('%d.%m.%Y %H:%M') if station.created_at else '',
                station.created_by.get_full_name() or station.created_by.username,
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="stations.xlsx"'
        return response


class TasksExportView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, View):
    """Выгрузка списка задач в .xlsx."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_task')

    def get(self, request, **kwargs):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Задачи'

        headers = ['ID', 'Станция', 'Описание', 'Статус', 'Ответственная организация', 'Ответственный сотрудник', 'Срок выполнения', 'Дата создания', 'Дата обновления']
        ws.append(headers)

        for task in Task.objects.filter(station__organization=self.get_org()).select_related('station', 'responsible_user').order_by('pk'):
            ws.append([
                task.pk,
                str(task.station),
                task.description,
                task.get_status_display(),
                task.responsible_organization,
                task.responsible_user.get_full_name() or task.responsible_user.username if task.responsible_user else '',
                task.due_date.strftime('%d.%m.%Y') if task.due_date else '',
                task.created_at.strftime('%d.%m.%Y %H:%M') if task.created_at else '',
                task.updated_at.strftime('%d.%m.%Y %H:%M') if task.updated_at else '',
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="tasks.xlsx"'
        return response


class EquipmentExportView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, View):
    """Выгрузка всего оборудования организации в .xlsx."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_equipment')

    def get(self, request, **kwargs):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Оборудование'

        headers = ['ID', 'Тип оборудования', 'Склад', 'Объект/станция', 'Заводской номер', 'Изготовитель', 'Дата изготовления', 'Дата добавления']
        ws.append(headers)

        for item in Equipment.objects.filter(warehouse__organization=self.get_org()).select_related('type', 'warehouse', 'station').order_by('pk'):
            ws.append([
                item.pk,
                item.type.title,
                item.warehouse.title,
                str(item.station) if item.station else '',
                item.factory_number,
                item.manufacturer,
                item.date_of_manufacture.strftime('%d.%m.%Y') if item.date_of_manufacture else '',
                item.added_at.strftime('%d.%m.%Y %H:%M') if item.added_at else '',
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="equipment.xlsx"'
        return response


class WarehouseEquipmentExportView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, View):
    """Выгрузка оборудования конкретного склада в .xlsx."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_equipment')

    def get(self, request, pk, **kwargs):
        warehouse = get_object_or_404(Warehouse, pk=pk, organization=self.get_org())

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Оборудование'

        headers = ['ID', 'Тип оборудования', 'Склад', 'Объект/станция', 'Заводской номер', 'Изготовитель', 'Дата изготовления', 'Дата добавления']
        ws.append(headers)

        for item in Equipment.objects.filter(warehouse=warehouse).select_related('type', 'warehouse', 'station').order_by('pk'):
            ws.append([
                item.pk,
                item.type.title,
                item.warehouse.title,
                str(item.station) if item.station else '',
                item.factory_number,
                item.manufacturer,
                item.date_of_manufacture.strftime('%d.%m.%Y') if item.date_of_manufacture else '',
                item.added_at.strftime('%d.%m.%Y %H:%M') if item.added_at else '',
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="warehouse_{warehouse.pk}_equipment.xlsx"'
        return response


class KnowledgeListView(OrgMixin, LoginRequiredMixin, ListView):
    """Список инструкций текущего пользователя. Загружается в contentPanel через AJAX."""

    model = UserKnowledge
    template_name = 'signal1520/knowledge_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        return UserKnowledge.objects.filter(user=self.request.user).select_related('knowledge')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        context['docs'] = qs.filter(knowledge__file__gt='')
        context['links'] = qs.filter(knowledge__external_link__gt='')
        return context


class KnowledgeCreateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, View):
    """Форма добавления инструкции: новый файл, существующий файл или ссылка."""

    template_name = 'signal1520/knowledge_form.html'

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        return self.request.user.has_perm('signal1520.add_userknowledge')

    def handle_no_permission(self):
        return redirect(reverse('authentication:error'))

    def _get_file_limit(self):
        try:
            return self.request.user.profile.knowledge_file_limit
        except Exception:
            return 10

    def _file_count(self):
        return Knowledge.objects.filter(created_by=self.request.user, file__gt='').count()

    def _existing_qs(self):
        used_ids = UserKnowledge.objects.filter(
            user=self.request.user
        ).values_list('knowledge_id', flat=True)
        return Knowledge.objects.filter(file__gt='').exclude(pk__in=used_ids)

    def _build_form(self, data=None, files=None):
        form = KnowledgeForm(data, files)
        form.fields['existing_knowledge'].queryset = self._existing_qs()
        return form

    def get(self, request, **kwargs):
        return render(request, self.template_name, {'form': self._build_form()})

    def post(self, request, **kwargs):
        form = self._build_form(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        existing = form.cleaned_data.get('existing_knowledge')
        new_file = form.cleaned_data.get('file')
        new_link = form.cleaned_data.get('external_link', '').strip()
        title = form.cleaned_data['title']
        description = form.cleaned_data.get('description', '')

        if existing:
            UserKnowledge.objects.create(
                user=request.user, knowledge=existing,
                title=title, description=description,
            )
        else:
            if new_file and self._file_count() >= self._get_file_limit():
                return render(request, 'signal1520/knowledge_limit.html')
            knowledge = Knowledge.objects.create(
                created_by=request.user,
                file=new_file or None,
                external_link=new_link,
            )
            UserKnowledge.objects.create(
                user=request.user, knowledge=knowledge,
                title=title, description=description,
            )

        logger.info('Инструкция добавлена: "%s" (user=%s)', title, request.user.username)
        messages.success(request, 'Инструкция успешно добавлена.')
        return redirect(reverse('signal1520:index', kwargs={'org_slug': self.kwargs['org_slug']}))


class KnowledgeDeleteView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, View):
    """AJAX-удаление инструкции пользователя. Файл удаляется физически только если больше никем не используется."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        return self.request.user.has_perm('signal1520.delete_userknowledge')

    def handle_no_permission(self):
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)

    def post(self, request, pk, **kwargs):
        uk = get_object_or_404(UserKnowledge, pk=pk, user=request.user)
        knowledge = uk.knowledge
        title = uk.title
        uk.delete()
        if not knowledge.user_knowledge.exists():
            if knowledge.file:
                knowledge.file.delete(save=False)
            knowledge.delete()
        logger.info('Инструкция удалена: "%s" (user=%s)', title, request.user.username)
        return JsonResponse({'success': True})


class WarehouseListView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Список складов организации с поиском."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_warehouse')

    model = Warehouse
    template_name = 'signal1520/warehouse_list.html'
    context_object_name = 'warehouses'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('responsible_user').prefetch_related('equipment')
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                models.Q(title__icontains=search_query) |
                models.Q(responsible_user__first_name__icontains=search_query) |
                models.Q(responsible_user__last_name__icontains=search_query) |
                models.Q(responsible_user__username__icontains=search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_add_warehouse'] = (
            self.request.user.is_superuser or
            self.request.user.has_perm('signal1520.add_warehouse')
        )
        return context

    def handle_no_permission(self):
        return redirect(reverse('authentication:error'))


class EquipmentListView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Список оборудования организации с поиском."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_equipment')

    model = Equipment
    template_name = 'signal1520/equipment_list.html'
    context_object_name = 'equipment_list'
    paginate_by = 10
    org_filter_field = 'warehouse__organization'

    def get_queryset(self):
        queryset = super().get_queryset().select_related('type', 'warehouse', 'station')
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                models.Q(type__title__icontains=search_query) |
                models.Q(warehouse__title__icontains=search_query) |
                models.Q(station__name__icontains=search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_add_equipment'] = (
            self.request.user.is_superuser or
            self.request.user.has_perm('signal1520.add_equipment')
        )
        context['can_add_type'] = (
            self.request.user.is_superuser or
            self.request.user.has_perm('signal1520.add_equipmenttype')
        )
        return context

    def handle_no_permission(self):
        return redirect(reverse('authentication:error'))


class WarehouseCreateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Форма создания склада."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.add_warehouse')

    model = Warehouse
    fields = 'title', 'responsible_user'
    template_name = 'signal1520/warehouse_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['responsible_user'].queryset = User.objects.filter(
            profile__organization=self.get_org()
        ).order_by('last_name', 'first_name', 'username')
        return form

    def form_valid(self, form):
        form.instance.organization = self.get_org()
        response = super().form_valid(form)
        logger.info('Склад создан: "%s" pk=%s (org=%s, user=%s)',
                    self.object.title, self.object.pk, self.get_org().slug, self.request.user.username)
        return response

    def get_success_url(self):
        return reverse('signal1520:warehouse_detail', kwargs=self.org_kwargs(pk=self.object.pk))

    def handle_no_permission(self):
        logger.warning('Отказ в доступе к созданию склада (user=%s)', self.request.user.username)
        return redirect(reverse('authentication:error'))


class WarehouseDetailView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Карточка склада с перечнем оборудования."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_warehouse')

    model = Warehouse
    template_name = 'signal1520/warehouse_details.html'
    context_object_name = 'warehouse'

    def get_queryset(self):
        return super().get_queryset().select_related('responsible_user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_edit'] = (
            self.request.user.is_superuser or
            self.request.user.has_perm('signal1520.change_warehouse')
        )
        context['can_add_equipment'] = (
            self.request.user.is_superuser or
            self.request.user.has_perm('signal1520.add_equipment')
        )
        equipment_qs = self.object.equipment.select_related('type', 'station').order_by('-added_at')
        paginator = Paginator(equipment_qs, 10)
        context['equipment_page'] = paginator.get_page(self.request.GET.get('page', 1))
        return context


class WarehouseUpdateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Форма редактирования склада."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.change_warehouse')

    model = Warehouse
    fields = 'title', 'responsible_user'
    template_name = 'signal1520/warehouse_update_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['responsible_user'].queryset = User.objects.filter(
            profile__organization=self.get_org()
        ).order_by('last_name', 'first_name', 'username')
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info('Склад обновлён: "%s" pk=%s (org=%s, user=%s)',
                    self.object.title, self.object.pk, self.get_org().slug, self.request.user.username)
        return response

    def get_success_url(self):
        return reverse('signal1520:warehouse_detail', kwargs=self.org_kwargs(pk=self.object.pk))

    def handle_no_permission(self):
        return redirect(reverse('authentication:error'))


class EquipmentCreateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Форма добавления единицы оборудования."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.add_equipment')

    model = Equipment
    fields = 'warehouse', 'station', 'type', 'factory_number', 'manufacturer', 'date_of_manufacture'
    template_name = 'signal1520/equipment_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        org = self.get_org()
        form.fields['warehouse'].queryset = Warehouse.objects.filter(organization=org)
        form.fields['station'].queryset = Station.objects.filter(organization=org)
        form.fields['type'].queryset = EquipmentType.objects.filter(organization=org)
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info('Оборудование добавлено: тип="%s", склад="%s" pk=%s (org=%s, user=%s)',
                    self.object.type, self.object.warehouse, self.object.pk,
                    self.get_org().slug, self.request.user.username)
        return response

    def get_success_url(self):
        return reverse('signal1520:equipment_detail', kwargs=self.org_kwargs(pk=self.object.pk))

    def handle_no_permission(self):
        logger.warning('Отказ в доступе к добавлению оборудования (user=%s)', self.request.user.username)
        return redirect(reverse('authentication:error'))


class EquipmentDetailView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Карточка единицы оборудования."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_equipment')

    model = Equipment
    template_name = 'signal1520/equipment_details.html'
    context_object_name = 'equipment'
    org_filter_field = 'warehouse__organization'

    def get_queryset(self):
        return super().get_queryset().select_related('type', 'warehouse', 'station')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_edit'] = (
            self.request.user.is_superuser or
            self.request.user.has_perm('signal1520.change_equipment')
        )
        context['can_view_warehouse'] = (
            self.request.user.is_superuser or
            self.request.user.has_perm('signal1520.view_warehouse')
        )
        return context


class EquipmentUpdateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Форма редактирования оборудования."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.change_equipment')

    model = Equipment
    fields = 'warehouse', 'station', 'type', 'factory_number', 'manufacturer', 'date_of_manufacture'
    template_name = 'signal1520/equipment_update_form.html'
    org_filter_field = 'warehouse__organization'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        org = self.get_org()
        form.fields['warehouse'].queryset = Warehouse.objects.filter(organization=org)
        form.fields['station'].queryset = Station.objects.filter(organization=org)
        form.fields['type'].queryset = EquipmentType.objects.filter(organization=org)
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info('Оборудование обновлено: тип="%s", склад="%s" pk=%s (org=%s, user=%s)',
                    self.object.type, self.object.warehouse, self.object.pk,
                    self.get_org().slug, self.request.user.username)
        return response

    def get_success_url(self):
        return reverse('signal1520:equipment_detail', kwargs=self.org_kwargs(pk=self.object.pk))

    def handle_no_permission(self):
        return redirect(reverse('authentication:error'))


class EquipmentTypeCreateView(OrgMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Форма добавления типа оборудования."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.add_equipmenttype')

    model = EquipmentType
    fields = ('title',)
    template_name = 'signal1520/equipment_type_form.html'

    def form_valid(self, form):
        form.instance.organization = self.get_org()
        response = super().form_valid(form)
        messages.success(self.request, f'Тип оборудования «{self.object.title}» успешно добавлен.')
        return response

    def get_success_url(self):
        return reverse('signal1520:index', kwargs={'org_slug': self.kwargs['org_slug']})

    def handle_no_permission(self):
        return redirect(reverse('authentication:error'))


class ContactView(OrgMixin, LoginRequiredMixin, View):
    """Форма обратной связи. Отправляет письмо на SUPPORT_EMAIL."""

    def _initial(self, user):
        return {
            'name': user.get_full_name() or user.username,
            'email': user.email,
        }

    def get(self, request, **kwargs):
        form = ContactForm(initial=self._initial(request.user))
        return render(request, 'signal1520/contact.html', {'form': form})

    def post(self, request, **kwargs):
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            message = form.cleaned_data['message']
            body = (
                f"Имя: {name}\n"
                f"Email: {email}\n"
                f"Пользователь: {request.user.username}\n"
                f"Организация: {getattr(request.user.profile.organization, 'name', '—')}\n"
                f"\n{message}"
            )
            try:
                send_mail(
                    subject=f"Обращение от {name}",
                    message=body,
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[settings.SUPPORT_EMAIL],
                    fail_silently=False,
                )
                logger.info('Обращение отправлено (user=%s, email=%s)', request.user.username, email)
            except Exception as exc:
                logger.error('Ошибка отправки обращения (user=%s): %s', request.user.username, exc)
            fresh_form = ContactForm(initial=self._initial(request.user))
            return render(request, 'signal1520/contact.html', {'form': fresh_form, 'success': True})
        return render(request, 'signal1520/contact.html', {'form': form})
