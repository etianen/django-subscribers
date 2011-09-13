"""Template tags used by django-subscribers."""

from django import template
from django.conf import settings
from django.contrib.sites.models import Site
from django.utils.html import escape


register = template.Library()


def get_host():
    """Attempts to resolve the host of the current website."""
    # Get the domain.
    if Site._meta.installed:
        domain = Site.objects.get_current.domain
    else:
        domain = settings.SITE_DOMAIN
    # Return the host prefix.
    return u"http://{domain}".format(
        domain = domain,
    )


@register.simple_tag()
def host():
    """
    Renders the host of the current website. This should be prefixed to all embedded links.
    
    If the sites framework is installed, then this shall be used to resolve the domain.
    Otherwise, a setting called SITE_DOMAIN is used.
    """
    return escape(get_host())