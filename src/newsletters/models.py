"""Models used by django-newsletters."""

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


class Recipient(models.Model):

    """A known email address."""

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


class DispatchedEmail(models.Model):

    """A batch mailing task."""

    date_created = models.DateTimeField(
        auto_now_add = True,
        db_index = True,
    )

    content_type = models.ForeignKey(
        ContentType,
    )
    
    manager_slug = models.CharField(
        db_index = True,
        max_length = 200,
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
    
    is_sent = models.BooleanField(
        default = False,
        db_index = True,
    )