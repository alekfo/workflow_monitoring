from django.urls import path
from .views import (TasksIndexView,
                    BugsListView,
                    StationListView,
                    StationDetailView,
                    StationCreateView,
                    BugCreateView,
                    BugDetailView,
                    BugUpdateView,
                    StationUpdateView,
                    MyBugsListView,
                    AlarmListView,
                    )

app_name = "signal1520"

urlpatterns = [
    path("", TasksIndexView.as_view(), name="index"),
    path("bugs/", BugsListView.as_view(), name="bugs_list"),
    path("bugs/my/", MyBugsListView.as_view(), name="bugs_list_my"),
    path("bugs/<int:pk>/", BugDetailView.as_view(), name="bug_details"),
    path("bugs/create/", BugCreateView.as_view(), name="create_bug"),
    path("bugs/<int:pk>/update/", BugUpdateView.as_view(), name="bug_update"),
    path("stations/", StationListView.as_view(), name="station_list"),
    path("stations/<int:pk>/", StationDetailView.as_view(), name="station_details"),
    path("stations/create/", StationCreateView.as_view(), name="create_station"),
    path("stations/<int:pk>/update/", StationUpdateView.as_view(), name="station_update"),
    path("alarms/", AlarmListView.as_view(), name="alarm_list"),
]
