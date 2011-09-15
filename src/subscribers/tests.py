"""Tests for the django-subscribers application."""

import datetime

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
        
        
class SubscribersTestModel1(TestModelBase):

    pass


str_pk_gen = 0;

def get_str_pk():
    global str_pk_gen
    str_pk_gen += 1;
    return str(str_pk_gen)
    
    
class SubscribersTestModel2(TestModelBase):

    id = models.CharField(
        primary_key = True,
        max_length = 100,
        default = get_str_pk,
        editable = False,
    )


class RegistrationTest(TestCase):

    def testRegistration(self):
        # Register the model and test.
        subscribers.register(SubscribersTestModel1)
        self.assertTrue(subscribers.is_registered(SubscribersTestModel1))
        self.assertRaises(RegistrationError, lambda: subscribers.register(SubscribersTestModel1))
        self.assertTrue(SubscribersTestModel1 in subscribers.get_registered_models())
        self.assertTrue(isinstance(subscribers.get_adapter(SubscribersTestModel1), subscribers.EmailAdapter))
        # Unregister the model and text.
        subscribers.unregister(SubscribersTestModel1)
        self.assertFalse(subscribers.is_registered(SubscribersTestModel1))
        self.assertRaises(RegistrationError, lambda: subscribers.unregister(SubscribersTestModel1))
        self.assertTrue(SubscribersTestModel1 not in subscribers.get_registered_models())
        self.assertRaises(RegistrationError, lambda: isinstance(subscribers.get_adapter(SubscribersTestModel1))) 


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
        
    def testSubscriberSubscribe(self):
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
        subscribers.register(SubscribersTestModel1)
        subscribers.register(SubscribersTestModel2)
        self.email1 = SubscribersTestModel1.objects.create(subject="Foo 1")
        self.email2 = SubscribersTestModel2.objects.create(subject="Foo 2")
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
        subscribers.unregister(SubscribersTestModel1)
        subscribers.unregister(SubscribersTestModel2)


# Tests that require a url conf.


class SubscribersTestAdminModel1(TestModelBase):

    pass
    
    
class SubscribersTestAdminModel2(TestModelBase):

    id = models.CharField(
        primary_key = True,
        max_length = 100,
        default = get_str_pk,
        editable = False,
    )


admin_site = admin.AdminSite()
admin_site.register(Subscriber, SubscriberAdmin)
admin_site.register(MailingList, MailingListAdmin)
admin_site.register(SubscribersTestAdminModel1, subscribers.EmailAdmin)
admin_site.register(SubscribersTestAdminModel2, subscribers.EmailAdmin)


urlpatterns = patterns("",
    
    url("^admin/", include(admin_site.urls)),

    url("^subscribers/", include("subscribers.urls")),

)

def handler404(request):
    return HttpResponseNotFound("Not found")
    
    
def handler500(request):
    return HttpResponseServerError("Server error")


class AdminTestBase(TestCase):

    urls = "subscribers.tests"

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


class SubscriberAdminTest(AdminTestBase):

    def setUp(self):
        super(SubscriberAdminTest, self).setUp()
        self.subscriber = Subscriber.objects.create(
            email = "foo@bar.com",
        )

    def testEmailsReceivedStatistic(self):
        response = self.client.get("/admin/subscribers/subscriber/")
        self.assertContains(response, "foo@bar.com")
        self.assertContains(response, "<td>0</td>")
        # Send the subscriber an email.
        email = SubscribersTestAdminModel1.objects.create(
            subject = "Foo bar 1",
        )
        subscribers.dispatch_email(email, self.subscriber)
        # Test that the email count is updated.
        response = self.client.get("/admin/subscribers/subscriber/")
        self.assertContains(response, "foo@bar.com")
        self.assertContains(response, "<td>1</td>")

    def testExportToCsvAction(self):
        response = self.client.post("/admin/subscribers/subscriber/", {
            "action": "export_selected_to_csv",
            "_selected_action": self.subscriber.id,
        })
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(response.content, "email,first name,last name,subscribed\r\nfoo@bar.com,,,1\r\n")

    def testSubscribeSelectedAction(self):
        self.subscriber.is_subscribed = False
        self.subscriber.save()
        self.assertEqual(Subscriber.objects.get(id=self.subscriber.id).is_subscribed, False)
        # Subscribe the subscriber.
        response = self.client.post("/admin/subscribers/subscriber/", {
            "action": "subscribe_selected",
            "_selected_action": self.subscriber.id,
        })
        self.assertRedirects(response, "/admin/subscribers/subscriber/")
        self.assertEqual(Subscriber.objects.get(id=self.subscriber.id).is_subscribed, True)
        
    def testUnsubscribeSelectedAction(self):
        # Unubscribe the subscriber.
        response = self.client.post("/admin/subscribers/subscriber/", {
            "action": "unsubscribe_selected",
            "_selected_action": self.subscriber.id,
        })
        self.assertRedirects(response, "/admin/subscribers/subscriber/")
        self.assertEqual(Subscriber.objects.get(id=self.subscriber.id).is_subscribed, False)
        
    def testAddSelectedToMailingListAction(self):
        mailing_list = MailingList.objects.create(
            name = "Foo list",
        )
        response = self.client.post("/admin/subscribers/subscriber/", {
            "action": "add_selected_to_foo_list_{pk}".format(pk=mailing_list.pk),
            "_selected_action": self.subscriber.id,
        })
        self.assertRedirects(response, "/admin/subscribers/subscriber/")
        self.assertEqual(list(Subscriber.objects.get(id=self.subscriber.id).mailing_lists.all()), [mailing_list])
        
    def testRemoveSelectedFromMailingListAction(self):
        mailing_list = MailingList.objects.create(
            name = "Foo list",
        )
        self.subscriber.mailing_lists.add(mailing_list)
        self.assertEqual(list(Subscriber.objects.get(id=self.subscriber.id).mailing_lists.all()), [mailing_list])
        response = self.client.post("/admin/subscribers/subscriber/", {
            "action": "remove_selected_from_foo_list_{pk}".format(pk=mailing_list.pk),
            "_selected_action": self.subscriber.id,
        })
        self.assertRedirects(response, "/admin/subscribers/subscriber/")
        self.assertEqual(list(Subscriber.objects.get(id=self.subscriber.id).mailing_lists.all()), [])


class MailingListAdminTest(AdminTestBase):

    def setUp(self):
        super(MailingListAdminTest, self).setUp()
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
        self.subscriber.mailing_lists.remove(self.mailing_list)
        response = self.client.get("/admin/subscribers/mailinglist/")
        self.assertContains(response, "Foo list")
        self.assertContains(response, "<td>0</td>")


class EmailAdminTest(AdminTestBase):
    
    def assertRecipientsStatisticWorks(self, model):
        model_slug = model.__name__.lower()
        email = model.objects.create(
            subject = "Foo bar 1",
        )
        response = self.client.get("/admin/auth/{model_slug}/".format(model_slug=model_slug))
        self.assertContains(response, "Foo bar 1")
        self.assertContains(response, "<td>0</td>")
        # Dispatch an email.
        subscriber = Subscriber.objects.create(
            email = "foo@bar.com",
        )
        subscribers.dispatch_email(email, subscriber)
        # Check that the statistics have updated.
        response = self.client.get("/admin/auth/{model_slug}/".format(model_slug=model_slug))
        self.assertContains(response, "Foo bar 1")
        self.assertContains(response, "<td>1</td>")
        
    def testRecipientStatistic(self):
        self.assertRecipientsStatisticWorks(SubscribersTestAdminModel1)
        
    def testRecipientStatisticStrPrimary(self):
        self.assertRecipientsStatisticWorks(SubscribersTestAdminModel2)
    
    def assertSaveAndTestWorks(self, model):
        model_slug = model.__name__.lower()
        # Create an object.
        response = self.client.post("/admin/auth/{model_slug}/add/".format(model_slug=model_slug), {
            "subject": "Foo bar 1",
            "_saveandtest": "1",
        })
        self.assertEqual(Subscriber.objects.count(), 0)
        self.assertEqual(model.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)  # No email created, as user does not have an email.
        obj = model.objects.get(subject="Foo bar 1")
        change_url = "/admin/auth/{model_slug}/{pk}/".format(model_slug=model_slug, pk=obj.pk)
        self.assertRedirects(response, change_url)
        # Add an email to our admin user.
        self.user.email = "foo@bar.com"
        self.user.save()
        # Create an object again.
        response = self.client.post("/admin/auth/{model_slug}/add/".format(model_slug=model_slug), {
            "subject": "Foo bar 2",
            "_saveandtest": "1",
        })
        self.assertEqual(Subscriber.objects.count(), 1)
        obj = model.objects.get(subject="Foo bar 2")
        change_url = "/admin/auth/{model_slug}/{pk}/".format(model_slug=model_slug, pk=obj.pk)
        self.assertRedirects(response, change_url)
        self.assertEqual(model.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Foo bar 2")
        # Change and test again.
        response = self.client.post(change_url, {
            "subject": "Foo bar 3",
            "_saveandtest": "1",
        })
        self.assertEqual(Subscriber.objects.count(), 1)
        self.assertRedirects(response, change_url)
        self.assertEqual(model.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].subject, "Foo bar 3")
    
    def testSaveAndTest(self):
        self.assertSaveAndTestWorks(SubscribersTestAdminModel1)
        
    def testSaveAndTestAddStrPrimary(self):
        self.assertSaveAndTestWorks(SubscribersTestAdminModel2)
    
    def assertSaveAndSendWorks(self, model):
        model_slug = model.__name__.lower()
        # Create two subscribers.
        subscriber1 = Subscriber.objects.create(
            email = "foo1@bar.com",
            is_subscribed = False,
        )
        subscriber2 = Subscriber.objects.create(
            email = "foo2@bar.com",
        )
        # Create a mailing list.
        mailing_list = MailingList.objects.create(
            name = "Foo list",
        )
        subscriber1.mailing_lists.add(mailing_list)
        # Create an email.
        email = model.objects.create(
            subject = "Foo bar 1",
        )
        change_url = "/admin/auth/{model_slug}/{pk}/".format(model_slug=model_slug, pk=email.pk)
        # Send to nobody.
        response = self.client.post(change_url, {
            "subject": "Foo bar 1",
            "_saveandsend": "1",
            "_send_to": "_nobody",
        })
        self.assertRedirects(response, change_url)
        self.assertEqual(len(subscribers.send_email_batch()), 0)
        self.assertEqual(len(mail.outbox), 0)
        # Send to a list with an unsubscribed person.
        response = self.client.post(change_url, {
            "subject": "Foo bar 1",
            "_saveandsend": "1",
            "_send_to": mailing_list.pk,
        })
        self.assertRedirects(response, "/admin/auth/{model_slug}/".format(model_slug=model_slug))
        self.assertEqual(len(subscribers.send_email_batch()), 0)
        self.assertEqual(len(mail.outbox), 0)
        # Subscribe the person again.
        subscriber1.is_subscribed = True
        subscriber1.save()
        # Send to a list.
        response = self.client.post(change_url, {
            "subject": "Foo bar 1",
            "_saveandsend": "1",
            "_send_to": mailing_list.pk,
        })
        self.assertRedirects(response, "/admin/auth/{model_slug}/".format(model_slug=model_slug))
        self.assertEqual(len(subscribers.send_email_batch()), 1)
        self.assertEqual(len(mail.outbox), 1)
        # Send to everyone, minus the people who have received it.
        response = self.client.post(change_url, {
            "subject": "Foo bar 1",
            "_saveandsend": "1",
            "_send_to": "_all",
        })
        self.assertRedirects(response, "/admin/auth/{model_slug}/".format(model_slug=model_slug))
        self.assertEqual(len(subscribers.send_email_batch()), 1)
        self.assertEqual(len(mail.outbox), 2)
        
    def testSaveAndSend(self):
        self.assertSaveAndSendWorks(SubscribersTestAdminModel1)
        
    def testSaveAndSendStrPrimary(self):
        self.assertSaveAndSendWorks(SubscribersTestAdminModel2)
        
    def assertCanStillSaveNormally(self, model):
        model_slug = model.__name__.lower()
        # Create an object.
        response = self.client.post("/admin/auth/{model_slug}/add/".format(model_slug=model_slug), {
            "subject": "Foo bar 1",
        })
        self.assertEqual(model.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        obj = model.objects.get(subject="Foo bar 1")
        change_url = "/admin/auth/{model_slug}/{pk}/".format(model_slug=model_slug, pk=obj.pk)
        self.assertRedirects(response, "/admin/auth/{model_slug}/".format(model_slug=model_slug))
        # Change and test again.
        response = self.client.post(change_url, {
            "subject": "Foo bar 2",
        })
        self.assertEqual(Subscriber.objects.count(), 0)
        self.assertRedirects(response, "/admin/auth/{model_slug}/".format(model_slug=model_slug))
        self.assertEqual(model.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        
    def testCanStillSaveNormally(self):
        self.assertCanStillSaveNormally(SubscribersTestAdminModel1)
        
    def testCanStillSaveNormallyStrPrimary(self):
        self.assertCanStillSaveNormally(SubscribersTestAdminModel2)
        
        
class EmailWorkflowsTest(TestCase):

    urls = "subscribers.tests"
    
    def setUp(self):
        subscribers.register(SubscribersTestModel1)
        subscribers.register(SubscribersTestModel2)
        self.email1 = SubscribersTestModel1.objects.create(subject="Foo 1")
        self.email2 = SubscribersTestModel2.objects.create(subject="Foo 1")
        self.subscriber1 = Subscriber.objects.subscribe(email="foo1@bar.com")
    
    def assertUnsubscribeWorkflowWorks(self, email):
        self.assertTrue(Subscriber.objects.get(id=self.subscriber1.id).is_subscribed)
        # Get the unsubscribe URL.
        unsubscribe_url = subscribers.get_adapter(email.__class__).get_unsubscribe_url(email, self.subscriber1)
        self.assertTrue(unsubscribe_url)  # Make sure the unsubscribe url is set.
        # Attempt to unsubscribe from an email that was never dispatched.
        self.assertEqual(self.client.get(unsubscribe_url).status_code, 404)
        # Dispatch the email.
        subscribers.dispatch_email(email, self.subscriber1)
        # Attempt to unsubscribe from an email that was never sent.
        self.assertEqual(self.client.get(unsubscribe_url).status_code, 404)
        # Send the emails.
        subscribers.send_email_batch()
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
        
    def testUnsubscribeWorkflow(self):
        self.assertUnsubscribeWorkflowWorks(self.email1)
        
    def testUnsubscribeWorkflowStrPrimaru(self):
        self.assertUnsubscribeWorkflowWorks(self.email2)
        
    def assertViewOnSiteWorks(self, email):
        view_url = subscribers.get_adapter(email.__class__).get_view_url(email, self.subscriber1)
        # Test that is doesn't let you in if the email has not been sent.
        response = self.client.get(view_url)
        self.assertEqual(response.status_code, 404)
        # Test that an unsent email does not work.
        subscribers.dispatch_email(email, self.subscriber1)
        response = self.client.get(view_url)
        self.assertEqual(response.status_code, 404)
        # Test that the view URL is valid.
        subscribers.send_email_batch()
        response = self.client.get(view_url)
        self.assertEqual(response.status_code, 200)
        # Test that the txt version also works.
        response = self.client.get(view_url + "txt/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        
    def testViewOnSite(self):
        self.assertViewOnSiteWorks(self.email1)
        
    def testViewOnSiteStrPrimary(self):
        self.assertViewOnSiteWorks(self.email2)
                
    def tearDown(self):
        subscribers.unregister(SubscribersTestModel1)
        subscribers.unregister(SubscribersTestModel2)
        
        
class SubscribeFormTest(TestCase):

    urls = "subscribers.tests"

    def testSubscribeFormRenders(self):
        response = self.client.get("/subscribers/subscribe/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "subscribers/subscribe.html")
        
    def testSubcribeFormValidates(self):
        response = self.client.post("/subscribers/subscribe/", {
            "email": "foo",
        })
        self.assertEqual(response.status_code, 200)  # i.e. not a redirect to the success page.
        
    def testSubscribeByName(self):
        response = self.client.post("/subscribers/subscribe/", {
            "name": "Foo Bar",
            "email": "foo@bar.com",
        })
        self.assertRedirects(response, "/subscribers/subscribe/success/")
        # Make sure the subscriber was created.
        subscriber = Subscriber.objects.get()
        self.assertEqual(subscriber.email, "foo@bar.com")
        self.assertTrue(subscriber.is_subscribed, True)
        self.assertEqual(subscriber.first_name, "Foo")
        self.assertEqual(subscriber.last_name, "Bar")
        
    def testSubscribeByNameParts(self):
        response = self.client.post("/subscribers/subscribe/", {
            "first_name": "Foo",
            "last_name": "Bar",
            "email": "foo@bar.com",
        })
        self.assertRedirects(response, "/subscribers/subscribe/success/")
        # Make sure the subscriber was created.
        subscriber = Subscriber.objects.get()
        self.assertEqual(subscriber.email, "foo@bar.com")
        self.assertTrue(subscriber.is_subscribed, True)
        self.assertEqual(subscriber.first_name, "Foo")
        self.assertEqual(subscriber.last_name, "Bar")
        
    def testResubscribeByName(self):
        subscriber = Subscriber.objects.create(
            email = "foo@bar.com",
            is_subscribed = False,
        )
        response = self.client.post("/subscribers/subscribe/", {
            "name": "Foo Bar",
            "email": "foo@bar.com",
        })
        self.assertRedirects(response, "/subscribers/subscribe/success/")
        # Make sure the subscriber was created.
        subscriber = Subscriber.objects.get()
        self.assertEqual(subscriber.email, "foo@bar.com")
        self.assertTrue(subscriber.is_subscribed, True)
        self.assertEqual(subscriber.first_name, "Foo")
        self.assertEqual(subscriber.last_name, "Bar")
        
    def testResubscribeByNameParts(self):
        subscriber = Subscriber.objects.create(
            email = "foo@bar.com",
            is_subscribed = False,
        )
        response = self.client.post("/subscribers/subscribe/", {
            "first_name": "Foo",
            "last_name": "Bar",
            "email": "foo@bar.com",
        })
        self.assertRedirects(response, "/subscribers/subscribe/success/")
        # Make sure the subscriber was created.
        subscriber = Subscriber.objects.get()
        self.assertEqual(subscriber.email, "foo@bar.com")
        self.assertTrue(subscriber.is_subscribed, True)
        self.assertEqual(subscriber.first_name, "Foo")
        self.assertEqual(subscriber.last_name, "Bar")
        
    def testSubscribeSuccessRenders(self):
        response = self.client.get("/subscribers/subscribe/success/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "subscribers/subscribe_success.html")