from django.shortcuts import render


def help_index(request):
    return render(request, 'help/index.html')


def ircd(request):
    return render(request, 'help/ircd.html', {'title': 'IRCd docs', 'subtitle': 'IRC daemon administration'})


def nickserv(request):
    return render(request, 'help/nickserv.html', {'title': 'NickServ','subtitle': 'Account management service'})


def chanserv(request):
    return render(request, 'help/chanserv.html', {'title': 'ChanServ', 'subtitle': 'Channel management service'})

def memoserv(request):
    return render(request, 'help/memoserv.html', {'title': 'MemoServ', 'subtitle': 'Memo management service'})


def operserv(request):
    return render(request, 'help/operserv.html', {'title': 'OperServ', 'subtitle': 'Operator management service'})