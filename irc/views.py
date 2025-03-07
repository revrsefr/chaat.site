from django.shortcuts import render

def webchat(request):
    return render(request, 'irc/webchat.html')
