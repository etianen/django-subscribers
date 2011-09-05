"""Views used by django-newsletters."""

from functools import wraps

from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect

from newsletters.models import DispatchedEmail, Recipient, STATUS_PENDING


def _patch_context(context, extra_context):
    """Updates the context with values from the extra context, if present."""
    if extra_context:
        for name, value in extra_context.iteritems():
            if callable(value):
                value = value()
            context[name] = value


def _protected_view(func):
    """Decorator that marks up a view as being protected by a secure hash."""
    @wraps(func)
    def do_protected_view(request, content_type_id, object_id, recipient_id, secure_hash):
        # Look up the content type.
        try:
            content_type = ContentType.objects.get_for_id(content_type_id)
        except ContentType.DoesNotExist:
            raise Http404("Invalid content type")
        # Look up the recipient.
        recipient = get_object_or_404(Recipient, id=recipient_id)
        # Look up the obj.
        model = content_type.model_class()
        obj = get_object_or_404(model, id=object_id)
        # Check that the email being referred to was actually sent.
        if not obj.dispatchedemail_set.filter(recipient=recipient).exclude(status=STATUS_PENDING).exists():
            raise Http404("No corresponding email was sent to this recipient.")
        # Wow, we've actually passed all the validation steps!
        return func(request, content_type, obj, recipient, secure_hash)
    return do_protected_view


@_protected_view
def unsubscribe(request, content_type, obj, recipient, secure_hash, template_name="newsletters/unsubscribe.html", extra_context=None):
    """Unsubscribes the user from this newsletter."""
    # Process unsubscribes.
    if request.method == "POST":
        recipient.is_subscribed = False
        recipient.save()
        return redirect("newsletters.views.unsubscribe_success", content_type.id, obj.pk, recipient.id, secure_hash)
    # No post request, so prompt the user to unsubscribe.
    context = {
        "obj": obj,
        "recipient": recipient,
    }
    _patch_context(context, extra_context)
    return render(request, template_name, context)
    

@_protected_view
def unsubscribe_success(request, content_type, obj, recipient, secure_hash, template_name="newsletters/unsubscribe_success.html", extra_context=None):
    """Displays the unsubscribe success message."""
    context = {
        "obj": obj,
        "recipient": recipient,
    }
    _patch_context(context, extra_context)
    return render(request, template_name, context)