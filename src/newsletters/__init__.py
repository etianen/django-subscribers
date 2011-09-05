"""
django-newsletters is a batch mailing utility for Django.

Includes list management, unsubscribe views and a background mailing service.

Developed by Dave Hall.

<http://www.etianen.com/>
"""

from newsletters.registration import default_email_manager, EmailAdapter


# Registration.
register = default_email_manager.register
unregister = default_email_manager.unregister
is_registered = default_email_manager.is_registered
get_registered_models = default_email_manager.get_registered_models
get_adapter = default_email_manager.get_adapter


# Dispatching email.
dispatch_email = default_email_manager.dispatch_email
send_email_batch_iter = default_email_manager.send_email_batch_iter
send_email_batch = default_email_manager.send_email_batch