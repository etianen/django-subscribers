"""Adapters for registering models with django-newsletters."""

from weakref import WeakValueDictionary

from django.db.models.signals import post_save, pre_delete

from newsletters.models import has_int_pk, DispatchedEmail


class EmailAdapter(object):

    """An adapter for generating an email from a model."""
        
    def __init__(self, model):
        """Initializes the email adapter."""
        self.model = model


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
                SentEmail,
                object_id_field = object_id_field,
            )
            model.dispatchedemail_set = generic_relation
            generic_relation.contribute_to_class(model, "dispatchedemail_set")
    
    def unregister(self, model):
        """
        Unregisters the given model with this email manager.
        
        If the given model is not registered with this email manager, a RegistrationError
        will be raised.
        """
        # Check for registration.
        if not self.is_registered(model):
            raise RegistrationError("{model!r} is not registered with this email manager".format(
                model = model,
            ))
        # Perform the unregistration.
        del self._registered_models[model]
        
    def get_registered_models(self):
        """Returns a sequence of models that have been registered with this email manager."""
        return self._registered_models.keys()
    
    def get_adapter(self, model):
        """Returns the adapter associated with the given model."""
        if self.is_registered(model):
            return self._registered_models[model]
        raise RegistrationError("{model!r} is not registered with this email manager".format(
            model = model,
        ))
        

# The default email manager.
default_email_manager = EmailManager("default")