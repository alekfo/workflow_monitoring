import io
import json

import openpyxl
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.models import Group
from django.views import View
from django.db import models
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin

from .models import Station, Task, Comment, Attachment, AlarmInfo, Road, System

class TasksIndexView(LoginRequiredMixin, View):
    """Главная страница приложения."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Отображает главную страницу с боковым меню и панелью контента."""
        return render(request, 'signal1520/index.html')

class StationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
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
        queryset = Station.objects.select_related('road', 'system').prefetch_related('tasks')
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                models.Q(name__icontains=search_query) |
                models.Q(road__title__icontains=search_query) |
                models.Q(distance__icontains=search_query) |
                models.Q(system__title__icontains=search_query)
            )
        return queryset

class StationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Детальная страница объекта (станции) с привязанными замечаниями."""

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

class StationCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Форма создания нового объекта (станции). Доступна суперпользователям и пользователям с правом add_station."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.add_station'):
            return True
        return False

    model = Station
    fields = "name", "road", "distance", "system", "description", "latitude", "longitude"
    # success_url = reverse_lazy("signal1520:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "signal1520:station_details",
            kwargs={"pk": self.object.pk}
        )

    def handle_no_permission(self):
        # Перенаправляем на страницу ошибки вместо 403
        return redirect(reverse('authentication:error'))

class StationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Форма редактирования существующего объекта (станции)."""

    def test_func(self):
        # return self.request.user.groups.filter(name="secret_group").exists()
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.change_station'):
            return True
        return False

    model = Station
    fields = "name", "road", "distance", "system", "description", "latitude", "longitude"
    template_name = 'signal1520/station_update_form.html'

    def get_success_url(self):
        return reverse(
            "signal1520:station_details",
            kwargs={"pk": self.object.pk}
        )


class BugsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Список всех замечаний с поиском по описанию, станции, организации и статусу."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.view_task'):
            return True
        return False

    model = Task
    template_name = 'signal1520/bug_list.html'
    paginate_by = 10

    # def get_template_names(self):
    #     if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    #         return ['signal1520/bug_list_ajax.html']
    #     return [self.template_name]

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

class MyBugsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Список замечаний, назначенных на текущего пользователя, с поддержкой поиска."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.view_task'):
            return True
        return False

    model = Task
    template_name = 'signal1520/my_bug_list.html'
    # paginate_by = 20  # опционально, если нужна пагинация

    # def get_template_names(self):
    #     if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    #         return ['signal1520/bug_list_ajax.html']
    #     return [self.template_name]

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

class BugDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Детальная страница замечания.

    GET  — отображает замечание с комментариями и вложениями.
    POST — обрабатывает три сценария:
           1. Загрузка файла-вложения.
           2. Добавление текстового комментария.
           3. Изменение статуса замечания (JSON-запрос от JavaScript).
    """

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.view_task'):
            return True
        return False

    template_name = 'signal1520/bug_details.html'
    queryset = Task.objects.select_related("responsible_user", "station").prefetch_related("comments", "attachments")
    context_object_name = "bug"  # имя, доступное в шаблоне

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # 1. --- Обработка вложения ---
        if 'file' in request.FILES:
            # Создаём вложение
            attachment = Attachment(
                task=self.object,
                file=request.FILES['file'],
                description=request.POST.get('description', '')
            )
            attachment.save()
            return redirect('signal1520:bug_details', pk=self.object.pk)

        # 2. Обработка добавления комментария (обычная форма)
        if 'comment_text' in request.POST:
            comment_text = request.POST.get('comment_text', '').strip()
            if comment_text:
                # Создаём комментарий, привязывая текущего пользователя
                Comment.objects.create(
                    task=self.object,
                    user=request.user,
                    body=comment_text
                )
            # Перенаправляем обратно на страницу с этим же замечанием
            return redirect('signal1520:bug_details', pk=self.object.pk)

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
        return JsonResponse({
            'success': True,
            'status': new_status,
            'status_display': self.object.get_status_display()
        })

class BugCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Форма создания нового замечания. Ответственный сотрудник устанавливается автоматически как текущий пользователь."""

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.add_task'):
            return True
        return False

    model = Task
    template_name = 'signal1520/bug_form.html'
    fields = "station", "description", "responsible_organization", "due_date"
    # success_url = reverse_lazy("signal1520:index")

    def form_valid(self, form):
        form.instance.responsible_user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "signal1520:bug_details",
            kwargs={"pk": self.object.pk}
        )

    def handle_no_permission(self):
        return redirect(reverse('authentication:error'))

class BugUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Форма редактирования замечания. Доступна суперпользователям, пользователям с правом change_task и ответственному сотруднику."""

    def test_func(self):
        # return self.request.user.groups.filter(name="secret_group").exists()
        bug = self.get_object()
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('signal1520.change_task'):
            return True
        if bug.responsible_user == self.request.user:
            return True
        return False

    model = Task
    fields = "station", "description", "status", "responsible_organization"
    template_name = 'signal1520/bug_update_form.html'

    def get_success_url(self):
        return reverse(
            "signal1520:bug_details",
            kwargs={"pk": self.object.pk}
        )

class AlarmListView(LoginRequiredMixin, ListView):
    """Список сигнальных событий (тревог) с поиском по номеру. Пагинация по 20 записей."""

    model = AlarmInfo
    template_name = 'signal1520/alarm_list.html'
    context_object_name = 'alarms'
    paginate_by = 10  # опционально

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(number__icontains=search_query)
        return queryset


class StationsExportView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Выгрузка списка станций в .xlsx."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_station')

    def get(self, request):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Станции'

        headers = ['ID', 'Наименование', 'Дорога/линия/район', 'Дистанция', 'Система', 'Описание', 'Широта', 'Долгота', 'Дата создания', 'Создал']
        ws.append(headers)

        for station in Station.objects.select_related('created_by', 'road', 'system').order_by('pk'):
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


class TasksExportView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Выгрузка списка замечаний в .xlsx."""

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('signal1520.view_task')

    def get(self, request):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Замечания'

        headers = ['ID', 'Станция', 'Описание', 'Статус', 'Ответственная организация', 'Ответственный сотрудник', 'Срок выполнения', 'Дата создания', 'Дата обновления']
        ws.append(headers)

        for task in Task.objects.select_related('station', 'responsible_user').order_by('pk'):
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
