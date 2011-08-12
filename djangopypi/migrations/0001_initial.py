# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Classifier'
        db.create_table('djangopypi_classifier', (
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255, primary_key=True)),
        ))
        db.send_create_signal('djangopypi', ['Classifier'])

        # Adding model 'Package'
        db.create_table('djangopypi_package', (
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255, primary_key=True)),
            ('auto_hide', self.gf('django.db.models.fields.BooleanField')(default=True, blank=True)),
            ('allow_comments', self.gf('django.db.models.fields.BooleanField')(default=True, blank=True)),
        ))
        db.send_create_signal('djangopypi', ['Package'])

        # Adding M2M table for field owners on 'Package'
        db.create_table('djangopypi_package_owners', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('package', models.ForeignKey(orm['djangopypi.package'], null=False)),
            ('group', models.ForeignKey(orm['auth.group'], null=False))
        ))
        db.create_unique('djangopypi_package_owners', ['package_id', 'group_id'])

        # Adding M2M table for field download_permissions on 'Package'
        db.create_table('djangopypi_package_download_permissions', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('package', models.ForeignKey(orm['djangopypi.package'], null=False)),
            ('group', models.ForeignKey(orm['auth.group'], null=False))
        ))
        db.create_unique('djangopypi_package_download_permissions', ['package_id', 'group_id'])

        # Adding M2M table for field maintainers on 'Package'
        db.create_table('djangopypi_package_maintainers', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('package', models.ForeignKey(orm['djangopypi.package'], null=False)),
            ('group', models.ForeignKey(orm['auth.group'], null=False))
        ))
        db.create_unique('djangopypi_package_maintainers', ['package_id', 'group_id'])

        # Adding model 'Release'
        db.create_table('djangopypi_release', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('package', self.gf('django.db.models.fields.related.ForeignKey')(related_name='releases', to=orm['djangopypi.Package'])),
            ('version', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('metadata_version', self.gf('django.db.models.fields.CharField')(default='1.0', max_length=64)),
            ('package_info', self.gf('djangopypi.models.PackageInfoField')()),
            ('hidden', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('djangopypi', ['Release'])

        # Adding unique constraint on 'Release', fields ['package', 'version']
        db.create_unique('djangopypi_release', ['package_id', 'version'])

        # Adding model 'Distribution'
        db.create_table('djangopypi_distribution', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('release', self.gf('django.db.models.fields.related.ForeignKey')(related_name='distributions', to=orm['djangopypi.Release'])),
            ('content', self.gf('django.db.models.fields.files.FileField')(max_length=100)),
            ('md5_digest', self.gf('django.db.models.fields.CharField')(max_length=32, blank=True)),
            ('filetype', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('pyversion', self.gf('django.db.models.fields.CharField')(max_length=16, blank=True)),
            ('comment', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('signature', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('uploader', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
        ))
        db.send_create_signal('djangopypi', ['Distribution'])

        # Adding unique constraint on 'Distribution', fields ['release', 'filetype', 'pyversion']
        db.create_unique('djangopypi_distribution', ['release_id', 'filetype', 'pyversion'])

        # Adding model 'Review'
        db.create_table('djangopypi_review', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('release', self.gf('django.db.models.fields.related.ForeignKey')(related_name='reviews', to=orm['djangopypi.Release'])),
            ('rating', self.gf('django.db.models.fields.PositiveSmallIntegerField')(blank=True)),
            ('comment', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal('djangopypi', ['Review'])


    def backwards(self, orm):
        
        # Deleting model 'Classifier'
        db.delete_table('djangopypi_classifier')

        # Deleting model 'Package'
        db.delete_table('djangopypi_package')

        # Removing M2M table for field owners on 'Package'
        db.delete_table('djangopypi_package_owners')

        # Removing M2M table for field download_permissions on 'Package'
        db.delete_table('djangopypi_package_download_permissions')

        # Removing M2M table for field maintainers on 'Package'
        db.delete_table('djangopypi_package_maintainers')

        # Deleting model 'Release'
        db.delete_table('djangopypi_release')

        # Removing unique constraint on 'Release', fields ['package', 'version']
        db.delete_unique('djangopypi_release', ['package_id', 'version'])

        # Deleting model 'Distribution'
        db.delete_table('djangopypi_distribution')

        # Removing unique constraint on 'Distribution', fields ['release', 'filetype', 'pyversion']
        db.delete_unique('djangopypi_distribution', ['release_id', 'filetype', 'pyversion'])

        # Deleting model 'Review'
        db.delete_table('djangopypi_review')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'djangopypi.classifier': {
            'Meta': {'object_name': 'Classifier'},
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'primary_key': 'True'})
        },
        'djangopypi.distribution': {
            'Meta': {'unique_together': "(('release', 'filetype', 'pyversion'),)", 'object_name': 'Distribution'},
            'comment': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'content': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'filetype': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'md5_digest': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'pyversion': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'release': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'distributions'", 'to': "orm['djangopypi.Release']"}),
            'signature': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'uploader': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'djangopypi.package': {
            'Meta': {'object_name': 'Package'},
            'allow_comments': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
            'auto_hide': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
            'download_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'maintainers': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'packages_maintained'", 'blank': 'True', 'to': "orm['auth.Group']"}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255', 'primary_key': 'True'}),
            'owners': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'packages_owned'", 'blank': 'True', 'to': "orm['auth.Group']"})
        },
        'djangopypi.release': {
            'Meta': {'unique_together': "(('package', 'version'),)", 'object_name': 'Release'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'hidden': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'metadata_version': ('django.db.models.fields.CharField', [], {'default': "'1.0'", 'max_length': '64'}),
            'package': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'releases'", 'to': "orm['djangopypi.Package']"}),
            'package_info': ('djangopypi.models.PackageInfoField', [], {}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'djangopypi.review': {
            'Meta': {'object_name': 'Review'},
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rating': ('django.db.models.fields.PositiveSmallIntegerField', [], {'blank': 'True'}),
            'release': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'reviews'", 'to': "orm['djangopypi.Release']"})
        }
    }

    complete_apps = ['djangopypi']
