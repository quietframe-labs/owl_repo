from django.urls import path
from . import views

app_name = 'dashboard_app'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('live-view/', views.live_view, name='live'),
    path('recordings/', views.recordings, name='recordings'),
    
]