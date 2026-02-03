from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from accounts.utils import verify_recaptcha
from .forms import ReportUserForm


@login_required
def report_user(request):
    if request.method == "POST":
        form = ReportUserForm(request.POST)
        if form.is_valid():
            recaptcha_token = request.POST.get("g-recaptcha-response")
            recaptcha_success, recaptcha_error = verify_recaptcha(recaptcha_token)
            if not recaptcha_success:
                error_detail = recaptcha_error or _("Please complete the reCAPTCHA challenge.")
                form.add_error(None, _("reCAPTCHA failed: %(detail)s") % {"detail": error_detail})
            else:
                reported_user = form.reported_user
                if reported_user == request.user:
                    form.add_error("reported_username", _("You cannot report yourself."))
                else:
                    report = form.save(commit=False)
                    report.reporter = request.user
                    report.reported = reported_user
                    report.save()
                    messages.success(request, _("Your report has been sent to the staff."))
                    return redirect("reports:report_user")
    else:
        form = ReportUserForm()

    return render(
        request,
        "reports/report_user.html",
        {
            "form": form,
            "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
        },
    )
