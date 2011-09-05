"""Models used by django-newsletters."""

import hashlib

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models


def has_int_pk(model):
    """Tests whether the given model has an integer primary key."""
    return (
        isinstance(model._meta.pk, (models.IntegerField, models.AutoField)) and
        not isinstance(model._meta.pk, models.BigIntegerField)
    )


class MailingList(models.Model):

    """A list of recipients."""

    date_created = models.DateTimeField(
        auto_now_add = True,
    )
    
    date_modified = models.DateTimeField(
        auto_now = True,
    )
    
    name = models.CharField(
        max_length = 200,
    )
    
    def __unicode__(self):
        """Returns the name of the mailing list."""
        return self.name
        
    class Meta:
        ordering = ("name",)
        
        
class RecipientManager(models.Manager):

    """Manager for the recipient model."""
    
    def subscribe(self, email, first_name=None, last_name=None):
        """Signs up the given recipient."""
        # Get the recipient.
        try:
            recipient = self.get(email=email)
        except self.model.DoesNotExist:
            recipient = Recipient(email=email)
        # Update the params.
        recipient.first_name = first_name or recipient.first_name
        recipient.last_name = last_name or recipient.last_name
        recipient.is_subscribed = True
        # Save the model.
        recipient.save()
        return recipient


class Recipient(models.Model):

    """A known email address."""
    
    objects = RecipientManager()

    date_created = models.DateTimeField(
        auto_now_add = True,
    )
    
    date_modified = models.DateTimeField(
        auto_now = True,
    )
    
    email = models.EmailField(
        unique = True,
    )
    
    first_name = models.CharField(
        max_length = 200,
        blank = True,
    )
    
    last_name = models.CharField(
        max_length = 200,
        blank = True,
    )
    
    is_subscribed = models.BooleanField(
        default = True,
        db_index = True,
    )
    
    mailing_lists = models.ManyToManyField(
        MailingList,
        blank = True,
    )
    
    def __unicode__(self):
        """Returns the email string for this address."""
        if self.first_name and self.last_name:
            return u"{first_name} {last_name} <{email}>".format(
                first_name = self.first_name,
                last_name = self.last_name,
                email = self.email,
            )
        if self.first_name:
            return u"{first_name} <{email}>".format(
                first_name = self.first_name,
                email = self.email,
            )
        if self.last_name:
            return u"{last_name} <{email}>".format(
                last_name = self.last_name,
                email = self.email,
            )
        return self.email
        
    class Meta:
        ordering = ("email",)


STATUS_PENDING = 0
STATUS_SENT = 1
STATUS_CANCELLED = 2
STATUS_UNSUBSCRIBED = 3
STATUS_ERROR = 4

STATUS_CHOICES = (
    (STATUS_PENDING, "Pending"),
    (STATUS_SENT, "Sent"),
    (STATUS_CANCELLED, "Cancelled"),
    (STATUS_UNSUBSCRIBED, "Unsubscribed"),
    (STATUS_ERROR, "Error"),
)


def get_secure_hash(obj, recipient):
    """
    Returns a secure hash that can be used to identify the recipient
    of the email email obj.
    """
    return hashlib.sha1(
        "$".join((
            settings.SECRET_KEY,
            unicode(obj.pk).encode("utf-8"),
            str(recipient.pk),
        ))
    ).hexdigest()


class DispatchedEmail(models.Model):

    """A batch mailing task."""

    date_created = models.DateTimeField(
        auto_now_add = True,
    )
    
    date_modified = models.DateTimeField(
        auto_now = True,
    )
    
    manager_slug = models.CharField(
        db_index = True,
        max_length = 200,
    )
    
    salt = models.CharField(
        max_length = 40,
    )
    
    content_type = models.ForeignKey(
        ContentType,
    )
    
    object_id = models.TextField()
    
    object_id_int = models.IntegerField(
        db_index = True,
        blank = True,
        null = True,
    )
    
    object = generic.GenericForeignKey()
    
    recipient = models.ForeignKey(
        Recipient,
    )
    
    from_email = models.CharField(
        max_length = 200,
        blank = True,
    )
    
    reply_to_email = models.CharField(
        max_length = 200,
        blank = True,
    )
    
    status = models.IntegerField(
        default = STATUS_PENDING,
        choices = STATUS_CHOICES,
        db_index = True,
    )
    
    status_message = models.TextField(
        blank = True,
    )
    
    def __unicode__(self):
        """Returns a unicode representation."""
        return unicode(self.object)
        
    class Meta:
        ordering = ("id",)