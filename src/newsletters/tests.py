"""Tests for the django-newsletters application."""

from django.db import models		
from django.test import TestCase
from django.conf.urls.defaults import *
from django.core import mail
from django.core.management import call_command
from django import template

import newsletters
from newsletters.models import Recipient, DispatchedEmail, STATUS_SENT, STATUS_UNSUBSCRIBED
from newsletters.registration import RegistrationError


class TestModelBase(models.Model):

    subject = models.CharField(
        max_length = 200,
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
        
    def testRecipientsubscribe(self):
        # Test that the recipient is created.
        recipient = Recipient.objects.subscribe(email="foo@bar.com")
        try:
            self.assertEqual(recipient.email, "foo@bar.com")
            self.assertTrue(recipient.pk)
            self.assertTrue(recipient.is_subscribed)
            # Test that the recipient can be updated.
            recipient = Recipient.objects.subscribe(email="foo@bar.com", first_name="Foo", last_name="Bar")
            self.assertEqual(recipient.first_name, "Foo")
            self.assertEqual(recipient.last_name, "Bar")
            # Test that there is still only one recipient.
            self.assertEqual(Recipient.objects.count(), 1)
            # Test that the recipient can be resubscribed.
            recipient.is_subscribed = False
            recipient.save()
            self.assertFalse(recipient.is_subscribed)
            recipient = Recipient.objects.subscribe(email="foo@bar.com")
            self.assertTrue(recipient.is_subscribed)
            # Test that there is still only one recipient.
            self.assertEqual(Recipient.objects.count(), 1)
            # Test that the stored name data is not overidden with blanks.
            self.assertEqual(recipient.first_name, "Foo")
            self.assertEqual(recipient.last_name, "Bar")
        finally:
            # Delete the recipient (cleanup).
            recipient.delete()
            
            
class DispatchedEmailTest(TestCase):

    def setUp(self):
        newsletters.register(TestModel1)
        newsletters.register(TestModel2)
        self.email1 = TestModel1.objects.create(subject="Foo 1")
        self.email2 = TestModel2.objects.create(subject="Foo 2")
        self.recipient1 = Recipient.objects.subscribe(email="foo1@bar.com")
        self.recipient2 = Recipient.objects.subscribe(email="foo2@bar.com")
        # Create the emails.
        for email in (self.email1, self.email2):
            for recipient in (self.recipient1, self.recipient2):
                newsletters.dispatch_email(email, recipient)

    def testDispatchEmail(self):
        # Make sure that the emails exist.
        self.assertEqual(DispatchedEmail.objects.count(), 4)
        # Send the emails.
        sent_emails = newsletters.send_email_batch()
        self.assertEqual(len([email for email in sent_emails if email.status == STATUS_SENT]), 4)
        self.assertEqual(len(mail.outbox), 4)
        # Check individual emails.
        self.assertEqual(mail.outbox[0].subject, "Foo 1")
        self.assertEqual(mail.outbox[0].to, [unicode(self.recipient1)])
        self.assertEqual(mail.outbox[1].subject, "Foo 1")
        self.assertEqual(mail.outbox[1].to, [unicode(self.recipient2)])
        self.assertEqual(mail.outbox[2].subject, "Foo 2")
        self.assertEqual(mail.outbox[2].to, [unicode(self.recipient1)])
        self.assertEqual(mail.outbox[3].subject, "Foo 2")
        self.assertEqual(mail.outbox[3].to, [unicode(self.recipient2)])
        # Make sure they aren't sent twice.
        sent_emails = newsletters.send_email_batch()
        self.assertEqual(len(sent_emails), 0)
        self.assertEqual(len(mail.outbox), 4)
    
    def testSendPartialBatch(self):
        sent_emails = newsletters.send_email_batch(2)
        self.assertEqual(len([email for email in sent_emails if email.status == STATUS_SENT]), 2)
        self.assertEqual(len(mail.outbox), 2)
    
    def testUnsubscribedEmailsNotSent(self):
        # Unsubscribe a recipient.
        self.recipient2.is_subscribed = False
        self.recipient2.save()
        # Send the emails.
        sent_emails = newsletters.send_email_batch()
        self.assertEqual(len([email for email in sent_emails if email.status == STATUS_SENT]), 2)
        self.assertEqual(len([email for email in sent_emails if email.status == STATUS_UNSUBSCRIBED]), 2)
        self.assertEqual(len(mail.outbox), 2)
        # Check individual emails.
        self.assertEqual(mail.outbox[0].subject, "Foo 1")
        self.assertEqual(mail.outbox[0].to, [unicode(self.recipient1)])
        self.assertEqual(mail.outbox[1].subject, "Foo 2")
        self.assertEqual(mail.outbox[1].to, [unicode(self.recipient1)])
        # Make sure they aren't sent twice.
        sent_emails = newsletters.send_email_batch()
        self.assertEqual(len(sent_emails), 0)
        self.assertEqual(len(mail.outbox), 2)
        
    def testSendEmailBatchCommand(self):
        call_command("sendemailbatch", verbosity=0)
        self.assertEqual(len(mail.outbox), 4)
        
    def testSendEmailBatchCommandWithBatchSize(self):
        call_command("sendemailbatch", "2", verbosity=0)
        self.assertEqual(len(mail.outbox), 2)
        
    def tearDown(self):
        newsletters.unregister(TestModel1)
        newsletters.unregister(TestModel2)


# Tests that require a url conf.

urlpatterns = patterns("",

    url("^newsletters/", include("newsletters.urls")),

)
        
        
class UnsubscribeTest(TestCase):

    urls = "newsletters.tests"
    
    def setUp(self):
        newsletters.register(TestModel1)
        newsletters.register(TestModel2)
        self.email1 = TestModel1.objects.create(subject="Foo 1")
        self.email2 = TestModel2.objects.create(subject="Foo 1")
        self.recipient1 = Recipient.objects.subscribe(email="foo1@bar.com")
    
    def assert404(self, callable):
        try:
            response = callable()
        except template.TemplateDoesNotExist as ex:
            self.assertEqual(ex.args[0], "404.html")
        else:
            self.assertEqual(response.status_code, 404)
            self.assertTemplateUsed(response, "404.html")
        
    def testUnsubscribeWorkflow(self):
        for email in (self.email1, self.email2):
            self.assertTrue(Recipient.objects.get(id=self.recipient1.id).is_subscribed)
            # Get the unsubscribe URL.
            params = newsletters.get_adapter(TestModel1).get_template_params(email, self.recipient1)
            unsubscribe_url = params["unsubscribe_url"]
            self.assertTrue(unsubscribe_url)  # Make sure the unsubscribe url is set.
            # Attempt to unsubscribe from an email that was never dispatched.
            self.assert404(lambda: self.client.get(unsubscribe_url))
            # Dispatch the email.
            newsletters.dispatch_email(email, self.recipient1)
            # Attempt to unsubscribe from an email that was never sent.
            self.assert404(lambda: self.client.get(unsubscribe_url))
            # Send the emails.
            sent_emails = newsletters.send_email_batch()
            # Try to unsubscribe again.
            response = self.client.get(unsubscribe_url)
            self.assertEqual(response.status_code, 200)
            response = self.client.post(unsubscribe_url, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "newsletters/unsubscribe_success.html")
            # See if the unsubscribe worked.
            self.assertFalse(Recipient.objects.get(id=self.recipient1.id).is_subscribed)
            # Re-subscribe the user.
            self.recipient1 = Recipient.objects.subscribe(email="foo1@bar.com")
    
    def tearDown(self):
        newsletters.unregister(TestModel1)