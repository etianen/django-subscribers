"""Adapters for registering models with django-subscribers."""

from weakref import WeakValueDictionary
from contextlib import closing

from django import template
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.urlresolvers import reverse, NoReverseMatch
from django.conf import settings

from subscribers.models import has_int_pk, get_secure_hash, DispatchedEmail, STATUS_PENDING, STATUS_SENT, STATUS_CANCELLED, STATUS_UNSUBSCRIBED, STATUS_ERROR


class EmailAdapter(object):

    """An adapter for generating an email from a model."""
        
    def __init__(self, model):
        """Initializes the email adapter."""
        self.model = model
        
    def get_subject(self, obj, subscriber):
        """Returns the subject for the email that this object represents."""
        return unicode(obj)
    
    def _get_template_name(self, obj, template_name):
        """Gets the appropriate fallback template name."""
        return [
            template_path.format(
                app_label = obj._meta.app_label,
                model = obj.__class__.__name__.lower(),
            ) for template_path in (
                "subscribers/{app_label}/{model}/email.txt",
                "subscribers/{app_label}/email.txt",
                "subscribers/email.txt",
            )
        ]
    
    def get_unsubscribe_url(self, obj, subscriber):
        """
        Returns the unsubscribe URL for the email this object represents.
        
        If it returns None, then no unsubscribe URL will be available in the
        template params.
        """
        try:
            return reverse("subscribers.views.unsubscribe", args=(
                ContentType.objects.get_for_model(obj).id,
                obj.pk,
                subscriber.pk,
                get_secure_hash(obj, subscriber),
            ))
        except NoReverseMatch:
            return None
        
    def get_template_params(self, obj, subscriber):
        """Returns the template params for the email this object represents."""
        # Get the base params.
        params = {
            "obj": obj,
            "subject": self.get_subject(obj, subscriber),
            "subscriber": subscriber,
            "MEDIA_URL": settings.MEDIA_URL,
            "STATIC_URL": settings.STATIC_URL,
        }
        # Add in the domain, if available.
        if Site._meta.installed:
            site = Site.objects.get_current()
            params["site"] = site
            params["domain"] = site.domain
            params["host"] = u"http://" + site.domain
        elif hasattr(settings, "SITE_DOMAIN"):
            params["domain"] = settings.SITE_DOMAIN
            params["host"] = u"http://" + settings.SITE_DOMAIN
        # Add in the unsubscribe url.
        unsubscribe_url = self.get_unsubscribe_url(obj, subscriber)
        if unsubscribe_url:
            params["unsubscribe_url"] = unsubscribe_url
        # All done.
        return params
    
    def get_content(self, obj, subscriber):
        """Returns the plain text content of the email that this object represents."""
        return template.loader.render_to_string(
            self._get_template_name(obj, "email.txt"),
            self.get_template_params(obj, subscriber),
        )
        
    def get_content_html(self, obj, subscriber):
        """
        Returns the HTML content of the email that this object represents.
        
        If it returns None, then the generated email will be plain text only.
        """
        return template.loader.render_to_string(
            self._get_template_name(obj, "email.html"),
            self.get_template_params(obj, subscriber),
        )
    
    def get_from_email(self, obj, subscriber):
        """Returns the from email address for this email."""
        return None
        
    def get_reply_to_email(self, obj, subscriber):
        """Returns the reply-to email address for this email, or None."""
        return None
        
    def get_email_headers(self, obj, subscriber):
        """Generates any additional headers for this email."""
        headers = {}
        # Add the reply-to.
        reply_to_email = self.get_reply_to_email(obj, subscriber)
        if reply_to_email:
            headers["Reply-To"] = unicode(reply_to_email)
        return headers
        
    def render_email(self, obj, subscriber):
        """Renders this object to an email."""
        # Create the email.
        email = EmailMultiAlternatives(
            subject = self.get_subject(obj, subscriber),
            body = self.get_content(obj, subscriber),
            to = (unicode(subscriber),),
            from_email = self.get_from_email(obj, subscriber),
        )
        # Add the HTML alternative.
        content_html = self.get_content_html(obj, subscriber)
        if content_html:
            email.attach_alternative(content_html, "text/html")
        # Add the headers.
        for name, value in self.get_email_headers(obj, subscriber).iteritems():
            email.headers[name] = value
        # All done.
        return email


class EmailManagerError(Exception):

    """Something went wrong with an email manager."""


class RegistrationError(EmailManagerError):

    """Something went wrong when registering a model with an email manager."""


class EmailManager(object):

    """An email manager used to register email adapters."""
    
    _created_managers = WeakValueDictionary()
    
    @classmethod
    def get_created_managers(cls):
        """Returns all created email managers."""
        return list(cls._created_managers.items())
    
    def __init__(self, manager_slug):
        """Initializes the email manager."""
        # Check the slug is unique for this manager.
        if manager_slug in self.__class__._created_managers:
            raise EmailManagerError("An email manager has already been created with the slug {manager_slug!r}".format(
                manager_slug = manager_slug,
            ))
        # Initialize thie engine.
        self._registered_models = {}
        self._manager_slug = manager_slug
        # Store a reference to this manager.
        self.__class__._created_managers[manager_slug] = self

    def is_registered(self, model):
        """Checks whether the given model is registered with this email manager."""
        return model in self._registered_models

    def register(self, model, adapter_cls=EmailAdapter, **field_overrides):
        """
        Registers the given model with this email manager.
        
        If the given model is already registered with this email manager, a
        RegistrationError will be raised.
        """
        # Check for existing registration.
        if self.is_registered(model):
            raise RegistrationError("{model!r} is already registered with this email manager".format(
                model = model,
            ))
        # Perform any customization.
        if field_overrides:
            adapter_cls = type("Custom" + adapter_cls.__name__, (adapter_cls,), field_overrides)
        # Perform the registration.
        adapter_obj = adapter_cls(model)
        self._registered_models[model] = adapter_obj
        # Add in a generic relation, if not exists.
        if not hasattr(model, "dispatchedemail_set"):
            if has_int_pk(model):
                object_id_field = "object_id_int"
            else:
                object_id_field = "object_id"
            generic_relation = generic.GenericRelation(
                DispatchedEmail,
                object_id_field = object_id_field,
            )
            model.dispatchedemail_set = generic_relation
            generic_relation.contribute_to_class(model, "dispatchedemail_set")
    
    def _assert_registered(self, model):
        """Raises a registration error if the given model is not registered with this email manager."""
        if not self.is_registered(model):
            raise RegistrationError("{model!r} is not registered with this email manager".format(
                model = model,
            ))
    
    def unregister(self, model):
        """
        Unregisters the given model with this email manager.
        
        If the given model is not registered with this email manager, a RegistrationError
        will be raised.
        """
        self._assert_registered(model)
        del self._registered_models[model]
        
    def get_registered_models(self):
        """Returns a sequence of models that have been registered with this email manager."""
        return self._registered_models.keys()
    
    def get_adapter(self, model):
        """Returns the adapter associated with the given model."""
        self._assert_registered(model)
        return self._registered_models[model]
        
    # Dispatching email.
    
    def dispatch_email(self, obj, subscriber):
        """Sends an email to the given subscriber."""
        self._assert_registered(obj.__class__)
        # Determine the integer object id.
        if has_int_pk(obj):
            object_id_int = int(obj.pk)
        else:
            object_id_int = None
        # Save the dispatched email.
        return DispatchedEmail.objects.create(
            manager_slug = self._manager_slug,
            content_type = ContentType.objects.get_for_model(obj),
            object_id = unicode(obj.pk),
            object_id_int = object_id_int,
            subscriber = subscriber,
        )
        
    def send_email_batch_iter(self, batch_size=None):
        """
        Sends a batch of emails.
        
        Returns an iterator of dispatched emails, some or all of which will
        be flagged as sent.
        """
        # Look up the emails to send.
        dispatched_emails = DispatchedEmail.objects.filter(
            manager_slug = self._manager_slug,
            status = STATUS_PENDING,
        ).select_related("subscriber")
        if batch_size is not None:
            dispatched_emails = dispatched_emails[:batch_size]
        # Aquire a connection.
        if dispatched_emails:
            with closing(get_connection()) as connection:
                connection.open()
                # Send the emails.
                for dispatched_email in dispatched_emails:
                    if dispatched_email.subscriber.is_subscribed:
                        content_type = ContentType.objects.get_for_id(dispatched_email.content_type_id)
                        model = content_type.model_class()
                        try:
                            obj = model._default_manager.get(pk=dispatched_email.object_id)
                        except model.DoesNotExist:
                            dispatched_email.status = STATUS_CANCELLED
                        else:
                            adapter = self.get_adapter(model)
                            # Generate the email.
                            email = adapter.render_email(obj, dispatched_email.subscriber)
                            email.connection = connection
                            # Try to send the email.
                            try:
                                email.send()
                            except Exception as ex:
                                dispatched_email.status = STATUS_ERROR
                                dispatched_email.status_message = str(ex)
                            else:
                                dispatched_email.status = STATUS_SENT
                    else:
                        dispatched_email.status = STATUS_UNSUBSCRIBED
                    # Save the result.
                    dispatched_email.save()
                    yield dispatched_email
    
    def send_email_batch(self, batch_size=None):
        """
        Sends a batch of emails.
        
        Returns an iterator of dispatched emails, some or all of which will
        be flagged as is_sent.
        """
        return list(self.send_email_batch_iter(batch_size))


# The default email manager.
default_email_manager = EmailManager("default")