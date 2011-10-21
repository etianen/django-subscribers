"""Views used by django-subscribers."""

from functools import wraps

from django.contrib.contenttypes.models import ContentType
from django.http import Http404, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect

from subscribers.forms import SubscribeForm
from subscribers.models import Subscriber, STATUS_PENDING
from subscribers.registration import default_email_manager


def _patch_context(context, extra_context):
    """Updates the context with values from the extra context, if present."""
    if extra_context:
        for name, value in extra_context.iteritems():
            if callable(value):
                value = value()
            context[name] = value


def subscribe(request, form_cls=SubscribeForm, template_name="subscribers/subscribe.html", extra_context=None):
    """Handles the subscribe success workflow."""
    if request.method == "POST":
        form = form_cls(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            Subscriber.objects.subscribe(
                email = data["email"],
                first_name = data["first_name"],
                last_name = data["last_name"],
            )
            return redirect("subscribers.views.subscribe_success")
    else:
        form = form_cls
    # Render the template.
    context = {
        "form": form,
    }
    _patch_context(context, extra_context)
    return render(request, template_name, context)
    
    
def subscribe_success(request, template_name="subscribers/subscribe_success.html", extra_context=None):
    """Displays the subscribe success message to the user."""
    context = {}
    _patch_context(context, extra_context)
    return render(request, template_name, context)


def _protected_view(func):
    """Decorator that marks up a view as being protected by a secure hash."""
    @wraps(func)
    def do_protected_view(request, content_type_id, object_id, subscriber_id, secure_hash, *args, **kwargs):
        # Look up the content type.
        try:
            content_type = ContentType.objects.get_for_id(content_type_id)
        except ContentType.DoesNotExist:
            raise Http404("Invalid content type")
        # Look up the subscriber.
        subscriber = get_object_or_404(Subscriber, id=subscriber_id)
        # Look up the obj.
        model = content_type.model_class()
        obj = get_object_or_404(model, id=object_id)
        # Check that the email being referred to was actually sent.
        if not obj.dispatchedemail_set.filter(subscriber=subscriber).exclude(status=STATUS_PENDING).exists():
            raise Http404("No corresponding email was sent to this subscriber.")
        # Wow, we've actually passed all the validation steps!
        return func(request, content_type, obj, subscriber, secure_hash)
    return do_protected_view


@_protected_view
def unsubscribe(request, content_type, obj, subscriber, secure_hash, template_name="subscribers/unsubscribe.html", extra_context=None):
    """Unsubscribes the user from this newsletter."""
    # Process unsubscribes.
    if request.method == "POST":
        subscriber.is_subscribed = False
        subscriber.save()
        return redirect("subscribers.views.unsubscribe_success", content_type.id, obj.pk, subscriber.id, secure_hash)
    # No post request, so prompt the user to unsubscribe.
    context = {
        "obj": obj,
        "subscriber": subscriber,
    }
    _patch_context(context, extra_context)
    return render(request, template_name, context)
    

@_protected_view
def unsubscribe_success(request, content_type, obj, subscriber, secure_hash, template_name="subscribers/unsubscribe_success.html", extra_context=None):
    """Displays the unsubscribe success message."""
    context = {
        "obj": obj,
        "subscriber": subscriber,
    }
    _patch_context(context, extra_context)
    return render(request, template_name, context)
    

@_protected_view    
def email_detail(request, content_type, obj, subscriber, secure_hash, email_manager=default_email_manager):
    """Displays the detail view of the email."""
    adapter = email_manager.get_adapter(obj.__class__)
    content = adapter.get_content_html(obj, subscriber).encode("utf-8")
    # Generate the response.
    response = HttpResponse(content)
    response["Content-Type"] = "text/html; charset=utf-8"
    response["Content-Length"] = str(len(content))
    return response
    
    
@_protected_view    
def email_detail_txt(request, content_type, obj, subscriber, secure_hash, email_manager=default_email_manager):
    """Displays the detail view of the email, in plain text format."""
    adapter = email_manager.get_adapter(obj.__class__)
    content = adapter.get_content(obj, subscriber).encode("utf-8")
    # Generate the response.
    response = HttpResponse(content)
    response["Content-Type"] = "text/plain; charset=utf-8"
    response["Content-Length"] = str(len(content))
    return response