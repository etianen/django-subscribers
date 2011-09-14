"""Sends a batch of emails."""

import datetime

from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from django.contrib import admin

from subscribers.registration import default_email_manager
from subscribers.models import STATUS_SENT, STATUS_CANCELLED, STATUS_UNSUBSCRIBED, STATUS_ERROR


admin.autodiscover()


class Command(BaseCommand):

    args = "<batch_size>"

    help = "Sends a batch of emails. Intended for inclusion in a crontab."
    
    def handle(self, *args, **kwargs):
        # Parse the batch size.
        if len(args) == 1:
            batch_size = int(args[0])
        elif len(args) == 0:
            batch_size = None
        else:
            raise CommandError("This command accepts zero or one arguments.")
        # Parse the verbosity.
        verbosity = int(kwargs.get("verbosity"))
        # Log an initial message.
        if verbosity >= 1:
            self.stdout.write("{timestamp} sending email batch...\n".format(
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
        # Send the email chunk.
        dispatched_count = 0
        sent_count = 0
        cancelled_count = 0
        unsubscribed_count = 0
        error_count = 0
        for dispatched_email in default_email_manager.send_email_batch_iter(batch_size):
            dispatched_count += 1
            log_params = {
                "subscriber": dispatched_email.subscriber,
                "model": ContentType.objects.get_for_id(dispatched_email.content_type_id).model_class().__name__,
                "pk": dispatched_email.object_id,
            }
            if dispatched_email.status == STATUS_SENT:
                sent_count += 1
                if verbosity >= 3:
                    self.stdout.write("  {subscriber} {model} #{pk} - Success\n".format(**log_params))
            if dispatched_email.status == STATUS_CANCELLED:
                cancelled_count += 1
                if verbosity >= 3:
                    self.stdout.write("  {subscriber} {model} #{pk} - Cancelled\n".format(**log_params))
            if dispatched_email.status == STATUS_UNSUBSCRIBED:
                unsubscribed_count += 1
                if verbosity >= 3:
                    self.stdout.write("  {subscriber} {model} #{pk} - Unsubscribed\n".format(**log_params))
            if dispatched_email.status == STATUS_ERROR:
                error_count += 1
                if verbosity >= 3:
                    self.stdout.write("  {subscriber} {model} #{pk} - Error\n".format(**log_params))
        # Report on the results.
        if verbosity >= 1:
            self.stdout.write("Processed {count} emails\n".format(
                count = dispatched_count,
            ))
        if verbosity >= 2:
            self.stdout.write("  {count} successful\n".format(
                count = sent_count,
            ))
            self.stdout.write("  {count} cancelled\n".format(
                count = cancelled_count,
            ))
            self.stdout.write("  {count} unsubscribed\n".format(
                count = unsubscribed_count,
            ))
            self.stdout.write("  {count} error\n".format(
                count = error_count,
            ))