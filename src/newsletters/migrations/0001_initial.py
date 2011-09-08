# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'MailingList'
        db.create_table('newsletters_mailinglist', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200)),
        ))
        db.send_create_signal('newsletters', ['MailingList'])

        # Adding model 'Recipient'
        db.create_table('newsletters_recipient', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(unique=True, max_length=75)),
            ('first_name', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('last_name', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('is_subscribed', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('newsletters', ['Recipient'])

        # Adding M2M table for field mailing_lists on 'Recipient'
        db.create_table('newsletters_recipient_mailing_lists', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('recipient', models.ForeignKey(orm['newsletters.recipient'], null=False)),
            ('mailinglist', models.ForeignKey(orm['newsletters.mailinglist'], null=False))
        ))
        db.create_unique('newsletters_recipient_mailing_lists', ['recipient_id', 'mailinglist_id'])

        # Adding model 'DispatchedEmail'
        db.create_table('newsletters_dispatchedemail', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('date_modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('manager_slug', self.gf('django.db.models.fields.CharField')(max_length=200, db_index=True)),
            ('salt', self.gf('django.db.models.fields.CharField')(max_length=40)),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('object_id', self.gf('django.db.models.fields.TextField')()),
            ('object_id_int', self.gf('django.db.models.fields.IntegerField')(db_index=True, null=True, blank=True)),
            ('recipient', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['newsletters.Recipient'])),
            ('status', self.gf('django.db.models.fields.IntegerField')(default=0, db_index=True)),
            ('status_message', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal('newsletters', ['DispatchedEmail'])


    def backwards(self, orm):
        
        # Deleting model 'MailingList'
        db.delete_table('newsletters_mailinglist')

        # Deleting model 'Recipient'
        db.delete_table('newsletters_recipient')

        # Removing M2M table for field mailing_lists on 'Recipient'
        db.delete_table('newsletters_recipient_mailing_lists')

        # Deleting model 'DispatchedEmail'
        db.delete_table('newsletters_dispatchedemail')


    models = {
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'newsletters.dispatchedemail': {
            'Meta': {'ordering': "('id',)", 'object_name': 'DispatchedEmail'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'manager_slug': ('django.db.models.fields.CharField', [], {'max_length': '200', 'db_index': 'True'}),
            'object_id': ('django.db.models.fields.TextField', [], {}),
            'object_id_int': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'recipient': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['newsletters.Recipient']"}),
            'salt': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'status_message': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        'newsletters.mailinglist': {
            'Meta': {'ordering': "('name',)", 'object_name': 'MailingList'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'newsletters.recipient': {
            'Meta': {'ordering': "('email',)", 'object_name': 'Recipient'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_subscribed': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'mailing_lists': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['newsletters.MailingList']", 'symmetrical': 'False', 'blank': 'True'})
        }
    }

    complete_apps = ['newsletters']
