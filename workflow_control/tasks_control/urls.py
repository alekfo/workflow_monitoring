from django.urls import path
from .views import (TasksIndexView,
                    BugsListView,
                    StationListView,
                    StationDetailView,
                    StationCreateView,
                    BugCreateView,
                    BugDetailView,
                    )

app_name = "tasks_control"

urlpatterns = [
    path("", TasksIndexView.as_view(), name="index"),
    path("bugs/", BugsListView.as_view(), name="bugs_list"),
    path("bugs/<int:pk>/", BugDetailView.as_view(), name="bug_details"),
    path("bugs/create", BugCreateView.as_view(), name="create_bug"),
    path("stations/", StationListView.as_view(), name="station_list"),
    path("stations/<int:pk>/", StationDetailView.as_view(), name="station_details"),
    path("stations/create", StationCreateView.as_view(), name="create_station"),
]
