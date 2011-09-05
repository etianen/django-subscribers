"""Adapters for registering models with django-newsletters."""

from weakref import WeakValueDictionary

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

from newsletters.models import has_int_pk, DispatchedEmail


class EmailAdapter(object):

    """An adapter for generating an email from a model."""
        
    def __init__(self, model):
        """Initializes the email adapter."""
        self.model = model
        
    def get_subject(self, obj):
        """Returns the subject for the email that this object represents."""
        return unicode(obj)
    
    def get_content(self, obj):
        """Returns the plain text content of the email that this object represents."""
        return unicode(obj)
        
    def get_content_html(self, obj):
        """
        Returns the HTML content of the email that this object represents.
        
        If None, then the email will be plain text only.
        """
        return None        


class EmailManagerError(Exception):

    """Something went wrong with an email manager."""


class RegistrationError(EmailManagerError):

    """Something went wrong when registering a model with an email manager."""


class EmailManager(object):

    """An email manager used to register."""
    
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
    
    def dispatch_email(self, recipient, obj, from_address="", reply_to_address=""):
        """Sends an email to the given recipient."""
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
            recipient = recipient,
            from_address = from_address,
            reply_to_address = reply_to_address,
        )
        

# The default email manager.
default_email_manager = EmailManager("default")