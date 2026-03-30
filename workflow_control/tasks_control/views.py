import json

from django.http import HttpResponse, HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.models import Group
from django.views import View
from django.db import models
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin

from .models import Station, Task, Comment, Attachment

class TasksIndexView(LoginRequiredMixin, View):

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, 'tasks_control/index.html')

class StationListView(LoginRequiredMixin, ListView):
    queryset = (
        Station.objects.prefetch_related('tasks')
    )

class StationDetailView(LoginRequiredMixin, DetailView):
    template_name = 'tasks_control/station_details.html'
    queryset = Station.objects.prefetch_related("tasks")
    context_object_name = "station"  # имя, доступное в шаблоне

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     # Проверяем, может ли пользователь редактировать станцию
    #     user = self.request.user
    #     station = self.get_object()
    #
    #     can_edit = (
    #             user.is_superuser or
    #             user.has_perm('tasks_control.change_station') or
    #             station.created_by == user
    #     )
    #     context['can_edit_station'] = can_edit
    #     return context

class StationCreateView(LoginRequiredMixin, CreateView):
    model = Station
    fields = "name", "road", "description", "latitude", "longitude"
    # success_url = reverse_lazy("tasks_control:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "tasks_control:station_details",
            kwargs={"pk": self.object.pk}
        )

class StationUpdateView(UserPassesTestMixin, UpdateView):
    def test_func(self):
        # return self.request.user.groups.filter(name="secret_group").exists()
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('tasks_control.change_station'):
            return True
        return False

    model = Station
    fields = "name", "road", "description", "latitude", "longitude"
    template_name = 'tasks_control/station_update_form.html'

    def get_success_url(self):
        return reverse(
            "tasks_control:station_details",
            kwargs={"pk": self.object.pk}
        )


class BugsListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = 'tasks_control/bug_list.html'
    # paginate_by = 20  # опционально, если нужна пагинация

    # def get_template_names(self):
    #     if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    #         return ['tasks_control/bug_list_ajax.html']
    #     return [self.template_name]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("responsible_user", "station")
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                models.Q(description__icontains=search_query) |
                models.Q(station__name__icontains=search_query) |
                models.Q(responsible_organization__icontains=search_query)
            )
        return queryset

class BugDetailView(LoginRequiredMixin, DetailView):
    template_name = 'tasks_control/bug_details.html'
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
            return redirect('tasks_control:bug_details', pk=self.object.pk)

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
            return redirect('tasks_control:bug_details', pk=self.object.pk)

        # 3. Обработка изменения статуса (JSON-запрос от JavaScript)
        # Проверка прав на изменение статуса
        if not (request.user.is_superuser or
                request.user.has_perm('tasks_control.change_task') or
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

class BugCreateView(LoginRequiredMixin, CreateView):
    model = Task
    template_name = 'tasks_control/bug_form.html'
    fields = "station", "description", "responsible_organization", "due_date"
    # success_url = reverse_lazy("tasks_control:index")

    def form_valid(self, form):
        form.instance.responsible_user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "tasks_control:bug_details",
            kwargs={"pk": self.object.pk}
        )

class BugUpdateView(UserPassesTestMixin, UpdateView):

    def test_func(self):
        # return self.request.user.groups.filter(name="secret_group").exists()
        bug = self.get_object()
        if self.request.user.is_superuser:
            return True
        if self.request.user.has_perm('tasks_control.change_task'):
            return True
        if bug.responsible_user == self.request.user:
            return True
        return False

    model = Task
    fields = "station", "description", "status", "responsible_organization"
    template_name = 'tasks_control/bug_update_form.html'

    def get_success_url(self):
        return reverse(
            "tasks_control:bug_details",
            kwargs={"pk": self.object.pk}
        )


