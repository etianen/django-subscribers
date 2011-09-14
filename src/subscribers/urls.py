"""URLs used by django-subscribers."""

from django.conf.urls.defaults import *


urlpatterns = patterns("subscribers.views",

    url("^unsubscribe/([^-]+)-([^-]+)-([^-]+)-([^/]+)/$", "unsubscribe", name="unsubscribe"),
    
    url("^unsubscribe/([^-]+)-([^-]+)-([^-]+)-([^/]+)/success/$", "unsubscribe_success", name="unsubscribe_success"),
    
    url("^([^-]+)-([^-]+)-([^-]+)-([^/]+)/$", "email_detail", name="email_detail"),
    
    url("^([^-]+)-([^-]+)-([^-]+)-([^/]+)/txt/$", "email_detail_txt", name="email_detail_txt"),

)