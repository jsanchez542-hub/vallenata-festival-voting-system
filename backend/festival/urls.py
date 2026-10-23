from django.urls import path

from . import views

app_name = "festival"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("editions/", views.EditionListView.as_view(), name="edition-list"),
    path("editions/<int:year>/", views.EditionDetailView.as_view(), name="edition-detail"),
    path("categories/", views.CurrentEditionRedirectView.as_view(), name="category-list"),
    path("categories/<int:pk>/", views.CategoryDetailView.as_view(), name="category-detail"),
    path("polls/", views.PollListView.as_view(), name="poll-list"),
    path("polls/<slug:slug>/", views.PollDetailView.as_view(), name="poll-detail"),
]
