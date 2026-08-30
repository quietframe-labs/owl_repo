from django.shortcuts import render
from django.http import HttpResponse

def index(request):
    context = {
        'message': 'testing_context_message', 
    }
    return render(request, 'dashboard_app/index.html', context)
