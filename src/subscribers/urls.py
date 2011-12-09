"""URLs used by django-subscribers."""

from django.conf.urls.defaults import *


urlpatterns = patterns("subscribers.views",

    url("^subscribe/$", "subscribe", name="subscribe"),
    
    url("^subscribe/success/$", "subscribe_success", name="subscribe_success"),

    url("^unsubscribe/(\d+)-([^-]+)-(\d+)-([^/]+)/$", "unsubscribe", name="unsubscribe"),
    
    url("^unsubscribe/(\d+)-([^-]+)-(\d+)-([^/]+)/success/$", "unsubscribe_success", name="unsubscribe_success"),
    
    url("^(\d+)-([^-]+)-(\d+)-([^/]+)/$", "email_detail", name="email_detail"),
    
    url("^(\d+)-([^-]+)-(\d+)-([^/]+)/txt/$", "email_detail_txt", name="email_detail_txt"),

)