"""Admin integration for newsletters."""

from functools import partial

from django.conf import settings
from django.contrib import admin
from django.db.models import Count

from newsletters.models import Recipient, MailingList


# Mix in watson search, if available.
if "watson" in settings.INSTALLED_APPS:
    import watson
    AdminBase = watson.SearchAdmin
else:
    AdminBase = admin.ModelAdmin


class RecipientAdmin(AdminBase):

    """Admin integration for recipients."""

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
        """Subscribes the selected recipients."""
        qs.update(is_subscribed=True)
        count = qs.count()
        self.message_user(request, u"{count} {item} marked as subscribed.".format(
            count = count,
            item = count != 1 and "recipients were" or "recipient was",
        ))
    subscribe_selected.short_description = "Mark selected recipients as subscribed"
    
    def unsubscribe_selected(self, request, qs):
        """Unsubscribes the selected recipients."""
        qs.update(is_subscribed=False)
        count = qs.count()
        self.message_user(request, u"{count} {item} marked as unsubscribed.".format(
            count = count,
            item = count != 1 and "recipients were" or "recipient was",
        ))
    unsubscribe_selected.short_description = "Mark selected recipients as unsubscribed"
    
    def add_selected_to_mailing_list(self, request, qs, mailing_list):
        """Adds the selected recipients to a mailing list."""
        for recipient in qs:
            recipient.mailing_lists.add(mailing_list)
            
    def remove_selected_from_mailing_list(self, request, qs, mailing_list):
        """Removes the selected recipients from a mailing list."""
        for recipient in qs:
            recipient.mailing_lists.remove(mailing_list)
    
    def get_actions(self, request):
        """Returns the actions this admin class supports."""
        actions = super(RecipientAdmin, self).get_actions(request)
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
                "Add selected recipients to {mailing_list}".format(
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
                "Remove selected recipients from {mailing_list}".format(
                    mailing_list = mailing_list,
                ),
            )
        # All done!
        return actions
    
    
admin.site.register(Recipient, RecipientAdmin)


class MailingListAdmin(AdminBase):

    """Admin integration for mailing lists."""
    
    search_fields = ("name",)
    
    list_display = ("name", "get_subscriber_count",)
    
    def get_subscriber_count(self, obj):
        """Returns the number of subscribers to this list."""
        return obj.recipient_set.filter(is_subscribed=True).count()
    get_subscriber_count.short_description = "Subscribers"
    
    
admin.site.register(MailingList, MailingListAdmin)