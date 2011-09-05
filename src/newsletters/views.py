"""Views used by django-newsletters."""

from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect

from newsletters.models import DispatchedEmail, Recipient, STATUS_PENDING


def unsubscribe(request, content_type_id, object_id, recipient_id, secure_hash, template_name="newsletters/unsubscribe.html", extra_context=None):
    """Unsubscribes the user from this newsletter."""
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
    # Wow, we've actually passed all the validation steps. Time to unsubscribe!
    if request.method == "POST":
        recipient.is_subscribed = False
        recipient.save()
        return redirect("newsletters.views.unsubscribe_success")
    # No post request, so prompt the user to unsubscribe.
    context = {
        "recipient": recipient,
    }
    if extra_context:
        for name, value in extra_context.iteritems():
            if callable(value):
                value = value()
            context[name] = value
    return render(request, template_name, context)
    
    
def unsubscribe_success(request):
    """Displays the unsubscribe success message."""