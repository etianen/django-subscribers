"""Tests for the django-newsletters application."""

from django.test import TestCase

from newsletters.models import Recipient


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