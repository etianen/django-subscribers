"""Admin integration for subscribers."""

import csv, cStringIO, datetime, time
from functools import partial, wraps

from django.conf import settings
from django.conf.urls.defaults import patterns, url
from django.contrib import admin, messages
from django.db.models import Count
from django.db import transaction
from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponse, Http404
from django.utils import formats

from subscribers.forms import ImportFromCsvForm
from subscribers.models import Subscriber, MailingList, has_int_pk
from subscribers.registration import default_email_manager


# Mix in watson search, if available.
if "watson" in settings.INSTALLED_APPS:
    import watson
    AdminBase = watson.SearchAdmin
else:
    AdminBase = admin.ModelAdmin
    
    
# Mix in reversion version control, if available.
if "reversion" in settings.INSTALLED_APPS:
    import reversion
    class VersionAdminBase(reversion.VersionAdmin, AdminBase):
        pass
else:
    VersionAdminBase = AdminBase


class SubscriberAdmin(AdminBase):

    """Admin integration for subscribers."""

    search_fields = ("email", "first_name", "last_name",)

    date_hierarchy = "date_created"

    actions = ("export_selected_to_csv", "subscribe_selected", "unsubscribe_selected",)

    list_display = ("email", "first_name", "last_name", "is_subscribed", "get_email_count", "date_created",)
    
    list_filter = ("is_subscribed", "mailing_lists",)
    
    filter_horizontal = ("mailing_lists",)
    
    fieldsets = (
        (None, {
            "fields": ("email", "first_name", "last_name", "is_subscribed",),
        }),
        ("Mailing lists", {
            "fields": ("mailing_lists",),
        }),
    )
    
    def queryset(self, request):
        """Returns the queryset to use for displaying the change list."""
        qs = super(SubscriberAdmin, self).queryset(request)
        qs = qs.annotate(
            email_count = Count("dispatchedemail"),
        )
        return qs
    
    def get_email_count(self, obj):
        """Returns the number of emails sent to this subscriber."""
        return obj.email_count
    get_email_count.short_description = "Emails received"
    
    # Custom views.
    
    def get_urls(self):
        """Returns the URL conf for this admin class."""
        urlpatterns = super(SubscriberAdmin, self).get_urls()
        admin_view = self.admin_site.admin_view
        urlpatterns = patterns("",
            url("^import/$", admin_view(self.import_from_csv), name="subscribers_subscriber_import"),
        ) + urlpatterns
        return urlpatterns
        
    @transaction.commit_on_success
    def import_from_csv(self, request):
        """Allows users to be imported from a CSV file."""
        # Process the form.
        if request.method == "POST":
            form = ImportFromCsvForm(request.POST, request.FILES)
            if form.is_valid():
                cleaned_rows = form.cleaned_data["rows"]
                invalid_rows = form.cleaned_data["invalid_rows"]
                # Import all cleaned rows.
                for data in cleaned_rows:
                    Subscriber.objects.subscribe(
                        email = data["email"],
                        first_name = data["first_name"],
                        last_name = data["last_name"],
                        is_subscribed = None,
                    )
                # Message the user.
                self.message_user(request, "Successfully imported {count} subscriber{pluralize}.".format(
                    count = len(cleaned_rows),
                    pluralize = len(cleaned_rows) != 1 and "s" or "",
                ))
                if invalid_rows:
                    messages.warning(request, "There {were} {count} error{pluralize} in your CSV file. The {first} error was on line {lineno}.".format(
                        were = len(invalid_rows) != 1 and "were" or "was",
                        count = len(invalid_rows),
                        pluralize = len(invalid_rows) != 1 and "s" or "",
                        lineno = invalid_rows[0][0],
                        first = len(invalid_rows) != 1 and "first" or "",
                    ))
                # Redirect.
                return redirect("{site}:subscribers_subscriber_changelist".format(
                    site = self.admin_site.name,
                ))
        else:
            form = ImportFromCsvForm()
        # Render the template.
        return render(request, "admin/subscribers/subscriber/import_from_csv.html", {
            "title": "Import subscribers from CSV",
            "form": form,
        })
    
    # Custom actions.
    
    def export_selected_to_csv(self, request, qs):
        """Renders the selected subscribers to CSV."""
        out = cStringIO.StringIO()
        # Render the preamble.
        writer = csv.writer(out)
        writer.writerow(("email", "first name", "last name", "subscribed",))
        # Render the CSV.
        for subscriber in qs:
            writer.writerow((
                subscriber.email.encode("utf-8"),
                subscriber.first_name.encode("utf-8"),
                subscriber.last_name.encode("utf-8"),
                str(int(subscriber.is_subscribed)),
            ))
        # Render the response.
        content = out.getvalue()
        response = HttpResponse(content)
        response["Content-Type"] = "text/csv; charset=utf-8"
        response["Content-Disposition"] = "attachment; filename=subscribers.csv"
        response["Content-Length"] = str(len(content))
        return response
    export_selected_to_csv.short_description = "Export selected subscribers to CSV"
    
    def subscribe_selected(self, request, qs):
        """Subscribes the selected subscribers."""
        for count, obj in enumerate(qs.iterator(), 1):  # HACK: Can't do this in an update, as it borks with the annotate clause in queryset().
            obj.is_subscribed = True
            obj.save()
        self.message_user(request, u"{count} {item} marked as subscribed.".format(
            count = count,
            item = count != 1 and "subscribers were" or "subscriber was",
        ))
    subscribe_selected.short_description = "Mark selected subscribers as subscribed"
    
    def unsubscribe_selected(self, request, qs):
        """Unsubscribes the selected subscribers."""
        for count, obj in enumerate(qs.iterator(), 1):  # HACK: Can't do this in an update, as it borks with the annotate clause in queryset().
            obj.is_subscribed = False
            obj.save()
        self.message_user(request, u"{count} {item} marked as unsubscribed.".format(
            count = count,
            item = count != 1 and "subscribers were" or "subscriber was",
        ))
    unsubscribe_selected.short_description = "Mark selected subscribers as unsubscribed"
    
    def add_selected_to_mailing_list(self, request, qs, mailing_list):
        """Adds the selected subscribers to a mailing list."""
        for subscriber in qs:
            subscriber.mailing_lists.add(mailing_list)
        count = len(qs)
        self.message_user(request, u"{count} {item} added to {mailing_list}.".format(
            count = count,
            item = count != 1 and "subscribers were" or "subscriber was",
            mailing_list = mailing_list,
        ))
            
    def remove_selected_from_mailing_list(self, request, qs, mailing_list):
        """Removes the selected subscribers from a mailing list."""
        for subscriber in qs:
            subscriber.mailing_lists.remove(mailing_list)
        count = len(qs)
        self.message_user(request, u"{count} {item} removed from {mailing_list}.".format(
            count = count,
            item = count != 1 and "subscribers were" or "subscriber was",
            mailing_list = mailing_list,
        ))
    
    def get_actions(self, request):
        """Returns the actions this admin class supports."""
        actions = super(SubscriberAdmin, self).get_actions(request)
        # Add in the mailing list actions.
        mailing_lists = [
            (u"{slug}_{pk}".format(
                slug = unicode(mailing_list).replace(" ", "_").lower(),
                pk = mailing_list.pk,
            ), mailing_list)
            for mailing_list
            in MailingList.objects.all()
        ]
        # Create the add actions.
        for mailing_list_slug, mailing_list in mailing_lists:
            add_action_name = u"add_selected_to_{mailing_list_slug}".format(
                mailing_list_slug = mailing_list_slug,
            )
            actions[add_action_name] = (
                partial(self.__class__.add_selected_to_mailing_list, mailing_list=mailing_list),
                add_action_name,
                "Add selected subscribers to {mailing_list}".format(
                    mailing_list = mailing_list,
                ),
            )
        # Create the remove actions.
        for mailing_list_slug, mailing_list in mailing_lists:
            remove_action_name = u"remove_selected_from_{mailing_list_slug}".format(
                mailing_list_slug = mailing_list_slug,
            )
            actions[remove_action_name] = (
                partial(self.__class__.remove_selected_from_mailing_list, mailing_list=mailing_list),
                remove_action_name,
                "Remove selected subscribers from {mailing_list}".format(
                    mailing_list = mailing_list,
                ),
            )
        # All done!
        return actions
    
    
admin.site.register(Subscriber, SubscriberAdmin)


class MailingListAdmin(AdminBase):

    """Admin integration for mailing lists."""
    
    search_fields = ("name",)
    
    list_display = ("name", "get_subscriber_count",)
    
    def queryset(self, request):
        """Returns the queryset to use for displaying the change list."""
        qs = super(MailingListAdmin, self).queryset(request)
        qs = qs.annotate(
            subscriber_count = Count("subscriber"),
        )
        return qs
    
    def get_subscriber_count(self, obj):
        """Returns the number of subscribers to this list."""
        return obj.subscriber_count
    get_subscriber_count.short_description = "Subscribers"
    
    
admin.site.register(MailingList, MailingListAdmin)


def allow_save_and_send(func):
    """Decorator that enables save and send on an admin view."""
    @wraps(func)
    def do_allow_save_and_send(admin_cls, request, obj, *args, **kwargs):
        def make_error_redirect(warning=None):
            admin_cls.message_user(request, u"The {model} \"{obj}\" was saved successfully.".format(
                    model = obj._meta.verbose_name,
                    obj = obj,
                ))
            if warning:
                messages.warning(request, warning)
            return redirect("{site}:{app}_{model}_change".format(
                site = admin_cls.admin_site.name,
                app = obj._meta.app_label,
                model = obj.__class__.__name__.lower(),
            ), obj.pk)
        if "_saveandsend" in request.POST:
            # Get the default list of subscribers.
            subscribers = Subscriber.objects.filter(
                is_subscribed = True,
            )
            # Try filtering by mailing list.
            send_to = request.POST["_send_to"]
            if send_to == "_nobody":
                return make_error_redirect(u"Please select a mailing list to send this {model} to.".format(
                    model = obj._meta.verbose_name,
                ))
            elif send_to == "_all":
                pass
            else:
                mailing_list = MailingList.objects.get(id=send_to)
                subscribers = subscribers.filter(mailing_lists=mailing_list)
            # Get the send date.
            if request.POST["_send_on_date"]:
                send_on_date = None
                for format in formats.get_format("DATE_INPUT_FORMATS"):
                    try:
                        send_on_date = datetime.date(*time.strptime(request.POST["_send_on_date"], format)[:3])
                    except ValueError:
                        pass
                    else:
                        break
                if send_on_date is None:
                    return make_error_redirect(u"Your date format was incorrect, so the email was not sent.")
            else:
                send_on_date = datetime.datetime.now().date()
            # Get the send time.
            if request.POST["_send_on_time"]:
                send_on_time = None
                for format in formats.get_format("TIME_INPUT_FORMATS"):
                    try:
                        send_on_time = datetime.time(*time.strptime(request.POST["_send_on_time"], format)[3:6])
                    except ValueError:
                        pass
                    else:
                        break
                if send_on_time is None:
                    return make_error_redirect(u"Your time format was incorrect, so the email was not sent.")
            else:
                send_on_time = datetime.datetime.now().time()
            # Get the send datetime.
            send_on_datetime = datetime.datetime.combine(send_on_date, send_on_time)
            # Calculate potential subscriber count.    
            potential_subscriber_count = subscribers.count()
            # Exclude subscribers who have already received the email.
            if has_int_pk(obj.__class__):
                subscribers_to_send = subscribers.exclude(
                    dispatchedemail__object_id_int = obj.pk,
                )
            else:
                subscribers_to_send = subscribers.exclude(
                    dispatchedemail__object_id = obj.pk,
                )
            subscribers_to_send = subscribers_to_send.distinct()
            # Send the email!
            subscriber_count = 0
            for subscriber in subscribers_to_send.iterator():
                subscriber_count += 1
                admin_cls.email_manager.dispatch_email(obj, subscriber, send_on_datetime)
            # Message the user.
            admin_cls.message_user(request, u"The {model} \"{obj}\" was saved successfully. An email will be sent to {count} subscriber{pluralize}.".format(
                model = obj._meta.verbose_name,
                obj = obj,
                count = subscriber_count,
                pluralize = subscriber_count != 1 and "s" or "",
            ))
            # Warn about unsent emails.
            if potential_subscriber_count > subscriber_count:
                unsent_count = potential_subscriber_count - subscriber_count
                messages.warning(request, u"{count} subscriber{pluralize} ignored, as they have already received this email.".format(
                    count = unsent_count,
                    pluralize = unsent_count != 1 and "s were" or " was",
                ))
            # Redirect the user.
            return redirect("{site}:{app}_{model}_changelist".format(
                site = admin_cls.admin_site.name,
                app = obj._meta.app_label,
                model = obj.__class__.__name__.lower(),
            ))
        return func(admin_cls, request, obj, *args, **kwargs)
    return do_allow_save_and_send


def allow_save_and_test(func):
    """Decorator that enables save and test on an admin view."""
    @wraps(func)
    def do_allow_save_and_test(admin_cls, request, obj, *args, **kwargs):
        if "_saveandtest" in request.POST:
            # Subscribe the admin user.
            user = request.user
            if user.email:
                # Get a subscriber object corresponding to the admin user.
                subscriber = Subscriber.objects.subscribe(
                    email = user.email,
                    first_name = user.first_name,
                    last_name = user.last_name,
                    force_save = False,
                )
                # Send the email.
                adapter = admin_cls.email_manager.get_adapter(obj.__class__)
                email_obj = adapter.render_email(obj, subscriber)
                email_obj.send()
                # Message the user.
                admin_cls.message_user(request, u"The {model} \"{obj}\" was saved successfully. A test email was sent to {email}.".format(
                    model = obj._meta.verbose_name,
                    obj = obj,
                    email = subscriber.email,
                ))
            else:
                admin_cls.message_user(request, u"The {model} \"{obj}\" was saved successfully.".format(
                    model = obj._meta.verbose_name,
                    obj = obj,
                ))
                messages.warning(request, u"Your admin account needs an email address before we can send a test email.")
            # Redirect the user.
            return redirect("{site}:{app}_{model}_change".format(
                site = admin_cls.admin_site.name,
                app = obj._meta.app_label,
                model = obj.__class__.__name__.lower(),
            ), obj.pk)
        return func(admin_cls, request, obj, *args, **kwargs)
    return do_allow_save_and_test


class EmailAdmin(VersionAdminBase):

    """Base class for newsletter models."""
    
    email_manager = default_email_manager
    
    list_display = ("__unicode__", "get_subscriber_count",)
    
    change_form_template = "admin/subscribers/newsletter/change_form.html"
    
    def __init__(self, *args, **kwargs):
        """Initializes the newsletter admin."""
        super(EmailAdmin, self).__init__(*args, **kwargs)
        # Autoregister.
        if not self.email_manager.is_registered(self.model):
            self.email_manager.register(self.model)
    
    def get_subscriber_count(self, obj):
        """Returns the number of subscribers who have received this email."""
        return obj.dispatchedemail_set.count()
    get_subscriber_count.short_description = "Recipients"
    
    @allow_save_and_send
    @allow_save_and_test
    def response_add(self, *args, **kwargs):
        return super(EmailAdmin, self).response_add(*args, **kwargs)
    
    @allow_save_and_send
    @allow_save_and_test        
    def response_change(self, *args, **kwargs):
        return super(EmailAdmin, self).response_change(*args, **kwargs)
        
    def render_change_form(self, request, context, *args, **kwargs):
        """Renders the change form."""
        context["send_to_options"] = MailingList.objects.all()
        return super(EmailAdmin, self).render_change_form(request, context, *args, **kwargs)
    
    def get_urls(self):
        urlpatterns = super(EmailAdmin, self).get_urls()
        urlpatterns = patterns("",
            url("^([^/]+)/preview/$", self.admin_site.admin_view(self.preview_view), name="{app_label}_{model_name}_preview".format(
                app_label = self.model._meta.app_label,
                model_name = self.model.__name__.lower(),
            )),
            url("^([^/]+)/preview-txt/$", self.admin_site.admin_view(self.preview_txt_view), name="{app_label}_{model_name}_preview_txt".format(
                app_label = self.model._meta.app_label,
                model_name = self.model.__name__.lower(),
            )),
        ) + urlpatterns
        return urlpatterns
    
    def preview_view(self, request, object_id):
        email = get_object_or_404(self.model, pk=object_id)
        adapter = self.email_manager.get_adapter(self.model)
        user = request.user
        if user.email:
            subscriber = Subscriber.objects.subscribe(
                email = user.email,
                first_name = user.first_name,
                last_name = user.last_name,
                force_save = False,
            )
            content = adapter.get_content_html(email, subscriber)
            response = HttpResponse(content)
            response["Content-Type"] = "text/html; charset=utf-8"
            return response
        else:
            raise Http404("Active user does not have an email address.")
        
    def preview_txt_view(self, request, object_id):
        email = get_object_or_404(self.model, pk=object_id)
        adapter = self.email_manager.get_adapter(self.model)
        user = request.user
        if user.email:
            subscriber = Subscriber.objects.subscribe(
                email = user.email,
                first_name = user.first_name,
                last_name = user.last_name,
                force_save = False,
            )
            content = adapter.get_content(email, subscriber)
            response = HttpResponse(content)
            response["Content-Type"] = "text/plain; charset=utf-8"
            return response
        else:
            raise Http404("Active user does not have an email address.")
        
    class Media:
        js = (
            settings.STATIC_URL + "admin/js/calendar.js",
            settings.STATIC_URL + "admin/js/admin/DateTimeShortcuts.js",
        )