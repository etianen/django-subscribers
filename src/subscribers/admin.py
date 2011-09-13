"""Admin integration for subscribers."""

from functools import partial, wraps

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count
from django.shortcuts import redirect

from subscribers.models import Subscriber, MailingList
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

    actions = ("subscribe_selected", "unsubscribe_selected",)

    list_display = ("email", "first_name", "last_name", "is_subscribed", "date_created",)
    
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
    
    # Custom actions.
    
    def subscribe_selected(self, request, qs):
        """Subscribes the selected subscribers."""
        qs.update(is_subscribed=True)
        count = qs.count()
        self.message_user(request, u"{count} {item} marked as subscribed.".format(
            count = count,
            item = count != 1 and "subscribers were" or "subscriber was",
        ))
    subscribe_selected.short_description = "Mark selected subscribers as subscribed"
    
    def unsubscribe_selected(self, request, qs):
        """Unsubscribes the selected subscribers."""
        qs.update(is_subscribed=False)
        count = qs.count()
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
            (unicode(mailing_list).replace(" ", "_").lower(), mailing_list)
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
                admin_cls.message_user(request, u"The {model} \"{obj}\" was saved successfully. A test email has been sent to {email}.".format(
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
    
    change_form_template = "admin/subscribers/newsletter/change_form.html"
    
    def __init__(self, *args, **kwargs):
        """Initializes the newsletter admin."""
        super(EmailAdmin, self).__init__(*args, **kwargs)
        # Autoregister.
        if not self.email_manager.is_registered(self.model):
            self.email_manager.register(self.model)
    
    @allow_save_and_test
    def response_add(self, *args, **kwargs):
        return super(EmailAdmin, self).response_add(*args, **kwargs)

    @allow_save_and_test        
    def response_change(self, *args, **kwargs):
        return super(EmailAdmin, self).response_change(*args, **kwargs)