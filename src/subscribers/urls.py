"""URLs used by django-subscribers."""

from django.conf.urls.defaults import *


urlpatterns = patterns("subscribers.views",

    url("^unsubscribe/([^-]+)-([^-]+)-([^-]+)-([^/]+)/$", "unsubscribe", name="unsubscribe"),
    
    url("^unsubscribe/([^-]+)-([^-]+)-([^-]+)-([^/]+)/success/$", "unsubscribe_success", name="unsubscribe_success"),

)