from django.http import HttpResponse, HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.models import Group
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin

from .models import Station

class TasksIndexView(View):

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, 'tasks_control/index.html')

class StationListView(ListView):
    queryset = (
        Station.objects.prefetch_related('tasks')
    )

class StationDetailView(DetailView):
    pass

class StationCreateView(CreateView):
    pass

class BugsListView(View):
    pass