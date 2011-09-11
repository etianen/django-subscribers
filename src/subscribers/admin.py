"""Admin integration for subscribers."""

from functools import partial

from django.conf import settings
from django.contrib import admin
from django.db.models import Count

from subscribers.models import Subscriber, MailingList


# Mix in watson search, if available.
if "watson" in settings.INSTALLED_APPS:
    import watson
    AdminBase = watson.SearchAdmin
else:
    AdminBase = admin.ModelAdmin


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
    
    def get_subscriber_count(self, obj):
        """Returns the number of subscribers to this list."""
        return obj.subscriber_set.filter(is_subscribed=True).count()
    get_subscriber_count.short_description = "Subscribers"
    
    
admin.site.register(MailingList, MailingListAdmin)