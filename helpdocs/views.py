from django.shortcuts import render


def help_index(request):
    return render(request, 'help/index.html')


def ircd(request):
    return render(request, 'help/ircd.html', {'title': 'IRCD Admin', 'subtitle': 'Server operator commands'})


def nickserv(request):
    return render(request, 'help/nickserv.html', {'title': 'NickServ'})


def chanserv(request):
    return render(request, 'help/chanserv.html', {'title': 'ChanServ'})


def memoserv(request):
    return render(request, 'help/memoserv.html', {'title': 'MemoServ'})


def operserv(request):
    return render(request, 'help/operserv.html', {'title': 'OperServ'})
