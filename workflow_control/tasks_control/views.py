from django.http import HttpResponse, HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.models import Group
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin

from .models import Station, Task

class TasksIndexView(LoginRequiredMixin, View):

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, 'tasks_control/index.html')

class StationListView(ListView):
    queryset = (
        Station.objects.prefetch_related('tasks')
    )

class StationDetailView(DetailView):
    template_name = 'tasks_control/station_details.html'
    queryset = Station.objects.prefetch_related("tasks")
    context_object_name = "station"  # имя, доступное в шаблоне

class StationCreateView(CreateView):
    model = Station
    fields = "name", "road", "description", "latitude", "longitude"
    success_url = reverse_lazy("tasks_control:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class BugsListView(ListView):
    model = Task  # явно указываем модель
    template_name = 'tasks_control/bug_list.html'
    queryset = (
        Task.objects.select_related("responsible_user", "station")
    )

class BugDetailView(DetailView):
    template_name = 'tasks_control/bug_details.html'
    queryset = Task.objects.select_related("responsible_user", "station").prefetch_related("comments", "attachments")
    context_object_name = "bug"  # имя, доступное в шаблоне

class BugCreateView(CreateView):
    model = Task
    template_name = 'tasks_control/bug_form.html'
    fields = "station", "description", "responsible_organization", "due_date"
    success_url = reverse_lazy("tasks_control:index")

    def form_valid(self, form):
        form.instance.responsible_user = self.request.user
        return super().form_valid(form)

