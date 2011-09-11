"""Tests for the django-subscribers application."""

from django.db import models		
from django.test import TestCase
from django.conf.urls.defaults import *
from django.contrib import admin
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django import template
from django.http import HttpResponseNotFound, HttpResponseServerError

import subscribers
from subscribers.admin import SubscriberAdmin, MailingListAdmin
from subscribers.models import Subscriber, MailingList, DispatchedEmail, STATUS_SENT, STATUS_UNSUBSCRIBED
from subscribers.registration import RegistrationError


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
        subscribers.register(TestModel1)
        self.assertTrue(subscribers.is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: subscribers.register(TestModel1))
        self.assertTrue(TestModel1 in subscribers.get_registered_models())
        self.assertTrue(isinstance(subscribers.get_adapter(TestModel1), subscribers.EmailAdapter))
        # Unregister the model and text.
        subscribers.unregister(TestModel1)
        self.assertFalse(subscribers.is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: subscribers.unregister(TestModel1))
        self.assertTrue(TestModel1 not in subscribers.get_registered_models())
        self.assertRaises(RegistrationError, lambda: isinstance(subscribers.get_adapter(TestModel1))) 


class SubscriberTest(TestCase):

    def testSubscriberEmailString(self):
        self.assertEqual(unicode(Subscriber(
            email = "foo@bar.com",
        )), "foo@bar.com")
        self.assertEqual(unicode(Subscriber(
            first_name = "Foo",
            email = "foo@bar.com",
        )), "Foo <foo@bar.com>")
        self.assertEqual(unicode(Subscriber(
            last_name = "Bar",
            email = "foo@bar.com",
        )), "Bar <foo@bar.com>")
        self.assertEqual(unicode(Subscriber(
            first_name = "Foo",
            last_name = "Bar",
            email = "foo@bar.com",
        )), "Foo Bar <foo@bar.com>")
        
    def testSubscribersubscribe(self):
        # Test that the subscriber is created.
        subscriber = Subscriber.objects.subscribe(email="foo@bar.com")
        try:
            self.assertEqual(subscriber.email, "foo@bar.com")
            self.assertTrue(subscriber.pk)
            self.assertTrue(subscriber.is_subscribed)
            # Test that the subscriber can be updated.
            subscriber = Subscriber.objects.subscribe(email="foo@bar.com", first_name="Foo", last_name="Bar")
            self.assertEqual(subscriber.first_name, "Foo")
            self.assertEqual(subscriber.last_name, "Bar")
            # Test that there is still only one subscriber.
            self.assertEqual(Subscriber.objects.count(), 1)
            # Test that the subscriber can be resubscribed.
            subscriber.is_subscribed = False
            subscriber.save()
            self.assertFalse(subscriber.is_subscribed)
            subscriber = Subscriber.objects.subscribe(email="foo@bar.com")
            self.assertTrue(subscriber.is_subscribed)
            # Test that there is still only one subscriber.
            self.assertEqual(Subscriber.objects.count(), 1)
            # Test that the stored name data is not overidden with blanks.
            self.assertEqual(subscriber.first_name, "Foo")
            self.assertEqual(subscriber.last_name, "Bar")
        finally:
            # Delete the subscriber (cleanup).
            subscriber.delete()
            
            
class DispatchedEmailTest(TestCase):

    def setUp(self):
        subscribers.register(TestModel1)
        subscribers.register(TestModel2)
        self.email1 = TestModel1.objects.create(subject="Foo 1")
        self.email2 = TestModel2.objects.create(subject="Foo 2")
        self.subscriber1 = Subscriber.objects.subscribe(email="foo1@bar.com")
        self.subscriber2 = Subscriber.objects.subscribe(email="foo2@bar.com")
        # Create the emails.
        for email in (self.email1, self.email2):
            for subscriber in (self.subscriber1, self.subscriber2):
                subscribers.dispatch_email(email, subscriber)

    def testDispatchEmail(self):
        # Make sure that the emails exist.
        self.assertEqual(DispatchedEmail.objects.count(), 4)
        # Send the emails.
        sent_emails = subscribers.send_email_batch()
        self.assertEqual(len([email for email in sent_emails if email.status == STATUS_SENT]), 4)
        self.assertEqual(len(mail.outbox), 4)
        # Check individual emails.
        self.assertEqual(mail.outbox[0].subject, "Foo 1")
        self.assertEqual(mail.outbox[0].to, [unicode(self.subscriber1)])
        self.assertEqual(mail.outbox[1].subject, "Foo 1")
        self.assertEqual(mail.outbox[1].to, [unicode(self.subscriber2)])
        self.assertEqual(mail.outbox[2].subject, "Foo 2")
        self.assertEqual(mail.outbox[2].to, [unicode(self.subscriber1)])
        self.assertEqual(mail.outbox[3].subject, "Foo 2")
        self.assertEqual(mail.outbox[3].to, [unicode(self.subscriber2)])
        # Make sure they aren't sent twice.
        sent_emails = subscribers.send_email_batch()
        self.assertEqual(len(sent_emails), 0)
        self.assertEqual(len(mail.outbox), 4)
    
    def testSendPartialBatch(self):
        sent_emails = subscribers.send_email_batch(2)
        self.assertEqual(len([email for email in sent_emails if email.status == STATUS_SENT]), 2)
        self.assertEqual(len(mail.outbox), 2)
    
    def testUnsubscribedEmailsNotSent(self):
        # Unsubscribe a subscriber.
        self.subscriber2.is_subscribed = False
        self.subscriber2.save()
        # Send the emails.
        sent_emails = subscribers.send_email_batch()
        self.assertEqual(len([email for email in sent_emails if email.status == STATUS_SENT]), 2)
        self.assertEqual(len([email for email in sent_emails if email.status == STATUS_UNSUBSCRIBED]), 2)
        self.assertEqual(len(mail.outbox), 2)
        # Check individual emails.
        self.assertEqual(mail.outbox[0].subject, "Foo 1")
        self.assertEqual(mail.outbox[0].to, [unicode(self.subscriber1)])
        self.assertEqual(mail.outbox[1].subject, "Foo 2")
        self.assertEqual(mail.outbox[1].to, [unicode(self.subscriber1)])
        # Make sure they aren't sent twice.
        sent_emails = subscribers.send_email_batch()
        self.assertEqual(len(sent_emails), 0)
        self.assertEqual(len(mail.outbox), 2)
        
    def testSendEmailBatchCommand(self):
        call_command("sendemailbatch", verbosity=0)
        self.assertEqual(len(mail.outbox), 4)
        
    def testSendEmailBatchCommandWithBatchSize(self):
        call_command("sendemailbatch", "2", verbosity=0)
        self.assertEqual(len(mail.outbox), 2)
        
    def tearDown(self):
        subscribers.unregister(TestModel1)
        subscribers.unregister(TestModel2)


# Tests that require a url conf.


admin_site = admin.AdminSite()
admin_site.register(Subscriber, SubscriberAdmin)
admin_site.register(MailingList, MailingListAdmin)


urlpatterns = patterns("",
    
    url("^admin/", include(admin_site.urls)),

    url("^subscribers/", include("subscribers.urls")),

)

def handler404(request):
    return HttpResponseNotFound("Not found")
    
    
def handler500(request):
    return HttpResponseServerError("Server error")


class MailingListAdminTest(TestCase):

    def setUp(self):
        # Create an admin user.
        self.user = User(
            username = "foo",
            is_staff = True,
            is_superuser = True,
        )
        self.user.set_password("bar")
        self.user.save()
        self.client.login(username="foo", password="bar")
        # Create a subscriber and a mailing list.
        self.subscriber = Subscriber.objects.create(
            email = "foo@bar.com",
        )
        self.mailing_list = MailingList.objects.create(
            name = "Foo list",
        )
        self.subscriber.mailing_lists.add(self.mailing_list)
        
    def testMailingListSubscriberCount(self):
        # Test a subscription.
        response = self.client.get("/admin/subscribers/mailinglist/")
        self.assertContains(response, "Foo list")
        self.assertContains(response, "<td>1</td>")
        # Test an unsubscription.
        self.subscriber.is_subscribed = False
        self.subscriber.save()
        response = self.client.get("/admin/subscribers/mailinglist/")
        self.assertContains(response, "Foo list")
        self.assertContains(response, "<td>0</td>")
        
        
class UnsubscribeTest(TestCase):

    urls = "subscribers.tests"
    
    def setUp(self):
        subscribers.register(TestModel1)
        subscribers.register(TestModel2)
        self.email1 = TestModel1.objects.create(subject="Foo 1")
        self.email2 = TestModel2.objects.create(subject="Foo 1")
        self.subscriber1 = Subscriber.objects.subscribe(email="foo1@bar.com")
        
    def testUnsubscribeWorkflow(self):
        for email in (self.email1, self.email2):
            self.assertTrue(Subscriber.objects.get(id=self.subscriber1.id).is_subscribed)
            # Get the unsubscribe URL.
            params = subscribers.get_adapter(TestModel1).get_template_params(email, self.subscriber1)
            unsubscribe_url = params["unsubscribe_url"]
            self.assertTrue(unsubscribe_url)  # Make sure the unsubscribe url is set.
            # Attempt to unsubscribe from an email that was never dispatched.
            self.assertEqual(self.client.get(unsubscribe_url).status_code, 404)
            # Dispatch the email.
            subscribers.dispatch_email(email, self.subscriber1)
            # Attempt to unsubscribe from an email that was never sent.
            self.assertEqual(self.client.get(unsubscribe_url).status_code, 404)
            # Send the emails.
            sent_emails = subscribers.send_email_batch()
            # Try to unsubscribe again.
            response = self.client.get(unsubscribe_url)
            self.assertEqual(response.status_code, 200)
            response = self.client.post(unsubscribe_url, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "subscribers/unsubscribe_success.html")
            # See if the unsubscribe worked.
            self.assertFalse(Subscriber.objects.get(id=self.subscriber1.id).is_subscribed)
            # Re-subscribe the user.
            self.subscriber1 = Subscriber.objects.subscribe(email="foo1@bar.com")
    
    def tearDown(self):
        subscribers.unregister(TestModel1)