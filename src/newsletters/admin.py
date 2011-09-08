"""Admin integration for newsletters."""

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

    list_display = ("email", "first_name", "last_name", "date_created",)
    
    list_filter = ("mailing_lists",)
    
    filter_horizontal = ("mailing_lists",)
    
    fieldsets = (
        (None, {
            "fields": ("email", "first_name", "last_name", "is_subscribed",),
        }),
        ("Mailing lists", {
            "fields": ("mailing_lists",),
        }),
    )
    
    
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