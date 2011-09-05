"""Tests for the django-newsletters application."""

from django.db import models		
from django.test import TestCase

import newsletters
from newsletters.models import Recipient
from newsletters.registration import RegistrationError


class TestModelBase(models.Model):

    subject = models.CharField(
        max_length = 200,
    )
    
    content = models.TextField(
        blank = True,
    )
        
    def __unicode__(self):
        return self.subject

    class Meta:
        abstract = True
        app_label = "auth"  # Hack: Cannot use an app_label that is under South control, due to http://south.aeracode.org/ticket/520
        
        
class TestModel1(TestModelBase):

    pass


str_pk_gen = 0;

def get_str_pk():
    global str_pk_gen
    str_pk_gen += 1;
    return str(str_pk_gen)
    
    
class TestModel2(TestModelBase):

    id = models.CharField(
        primary_key = True,
        max_length = 100,
        default = get_str_pk
    )


class RegistrationTest(TestCase):

    def testRegistration(self):
        # Register the model and test.
        newsletters.register(TestModel1)
        self.assertTrue(newsletters.is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: newsletters.register(TestModel1))
        self.assertTrue(TestModel1 in newsletters.get_registered_models())
        self.assertTrue(isinstance(newsletters.get_adapter(TestModel1), newsletters.EmailAdapter))
        # Unregister the model and text.
        newsletters.unregister(TestModel1)
        self.assertFalse(newsletters.is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: newsletters.unregister(TestModel1))
        self.assertTrue(TestModel1 not in newsletters.get_registered_models())
        self.assertRaises(RegistrationError, lambda: isinstance(newsletters.get_adapter(TestModel1))) 


class RecipientTest(TestCase):

    def testRecipientEmailString(self):
        self.assertEqual(unicode(Recipient(
            email = "foo@bar.com",
        )), "foo@bar.com")
        self.assertEqual(unicode(Recipient(
            first_name = "Foo",
            email = "foo@bar.com",
        )), "Foo <foo@bar.com>")
        self.assertEqual(unicode(Recipient(
            last_name = "Bar",
            email = "foo@bar.com",
        )), "Bar <foo@bar.com>")
        self.assertEqual(unicode(Recipient(
            first_name = "Foo",
            last_name = "Bar",
            email = "foo@bar.com",
        )), "Foo Bar <foo@bar.com>")
        
    def testRecipientSignup(self):
        # Test that the recipient is created.
        recipient = Recipient.objects.signup(email="foo@bar.com")
        try:
            self.assertEqual(recipient.email, "foo@bar.com")
            self.assertTrue(recipient.pk)
            self.assertTrue(recipient.is_subscribed)
            # Test that the recipient can be updated.
            recipient = Recipient.objects.signup(email="foo@bar.com", first_name="Foo", last_name="Bar")
            self.assertEqual(recipient.first_name, "Foo")
            self.assertEqual(recipient.last_name, "Bar")
            # Test that there is still only one recipient.
            self.assertEqual(Recipient.objects.count(), 1)
            # Test that the recipient can be resubscribed.
            recipient.is_subscribed = False
            recipient.save()
            self.assertFalse(recipient.is_subscribed)
            recipient = Recipient.objects.signup(email="foo@bar.com")
            self.assertTrue(recipient.is_subscribed)
            # Test that there is still only one recipient.
            self.assertEqual(Recipient.objects.count(), 1)
            # Test that the stored name data is not overidden with blanks.
            self.assertEqual(recipient.first_name, "Foo")
            self.assertEqual(recipient.last_name, "Bar")
        finally:
            # Delete the recipient (cleanup).
            recipient.delete()