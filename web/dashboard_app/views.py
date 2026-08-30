from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse

@login_required
def dashboard(request):
    return render(request, 'dashboard_app/dashboard.html')

@login_required
def live_view(request):
    return render(request, 'dashboard_app/live_view.html')

@login_required
def recordings(request):
    return render(request, 'dashboard_app/recordings.html')