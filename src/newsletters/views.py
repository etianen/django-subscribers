"""Views used by django-newsletters."""

from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import render, get_object_or_404

from newsletters.models import DispatchedEmail, Recipient, STATUS_PENDING


def unsubscribe(request, content_type_id, object_id, recipient_id, secure_hash):
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
    
    
    
    
def unsubscribe_success(request):
    pass