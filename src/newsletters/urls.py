"""URLs used by django-newsletters."""

from django.conf.urls.defaults import *


urlpatterns = patterns("newsletters.views",

    url("^unsubscribe/([^-]+)-([^-]+)-([^-]+)-([^/]+)/$", "unsubscribe", name="unsubscribe"),
    
    url("^unsubscribe/([^-]+)-([^-]+)-([^-]+)-([^/]+)/success/$", "unsubscribe_success", name="unsubscribe_success"),

)