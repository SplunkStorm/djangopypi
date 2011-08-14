import os
import logging

from django.db import models
from django.core.files.storage import FileSystemStorage
from django.utils.translation import ugettext_lazy as _
from django.utils import simplejson as json
from django.utils.datastructures import MultiValueDict
from django.contrib.auth.models import User, Group
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.conf import settings

from djangopypi import conf

class PackageInfoField(models.Field):
    description = u'Python Package Information Field'
    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        kwargs['editable'] = False
        super(PackageInfoField,self).__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, basestring):
            if value:
                return MultiValueDict(json.loads(value))
            else:
                return MultiValueDict()
        if isinstance(value, dict):
            return MultiValueDict(value)
        if isinstance(value,MultiValueDict):
            return value
        raise ValueError('Unexpected value encountered when converting data to python')

    def get_prep_value(self, value):
        if isinstance(value,MultiValueDict):
            return json.dumps(dict(value.iterlists()))
        if isinstance(value, dict):
            return json.dumps(value)
        if isinstance(value, basestring) or value is None:
            return value

        raise ValueError('Unexpected value encountered when preparing for database')

    def get_internal_type(self):
        return 'TextField'

class Classifier(models.Model):
    name = models.CharField(max_length=255, primary_key=True)

    class Meta:
        verbose_name = _(u"classifier")
        verbose_name_plural = _(u"classifiers")
        ordering = ('name',)

    def __unicode__(self):
        return self.name

class Package(models.Model):
    name = models.CharField(max_length=255, unique=True, primary_key=True,
                            editable=False)
    auto_hide = models.BooleanField(default=True, blank=False)
    allow_comments = models.BooleanField(default=True, blank=False)
    owners = models.ManyToManyField(Group, blank=True,
                                    related_name="packages_owned")
    download_permissions = models.ManyToManyField(Group, blank=True,
        help_text="""
            Determines which groups can download this package -
            selecting no groups at all will allow anyone access to the package.
        """
    )
    maintainers = models.ManyToManyField(Group, blank=True,
                                         related_name="packages_maintained")

    class Meta:
        verbose_name = _(u"package")
        verbose_name_plural = _(u"packages")
        get_latest_by = "releases__latest"
        ordering = ['name',]

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ('djangopypi-package', (), {'package': self.name})

    @property
    def latest(self):
        try:
            return self.releases.latest()
        except Release.DoesNotExist:
            return None

    def get_release(self, version):
        """Return the release object for version, or None"""
        try:
            return self.releases.get(version=version)
        except Release.DoesNotExist:
            return None
    
    def delete(self,*args,**kwargs):
        for release in self.releases.all():
            release.delete()
        super(Package,self).delete(*args,**kwargs)

class Release(models.Model):
    package = models.ForeignKey(Package, related_name="releases", editable=False)
    version = models.CharField(max_length=128, editable=False)
    metadata_version = models.CharField(max_length=64, default='1.0')
    package_info = PackageInfoField(blank=False)
    hidden = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name = _(u"release")
        verbose_name_plural = _(u"releases")
        unique_together = ("package", "version")
        get_latest_by = 'created'
        ordering = ['-created']

    def __unicode__(self):
        return self.release_name

    @property
    def release_name(self):
        return u"%s-%s" % (self.package.name, self.version)

    @property
    def summary(self):
        return self.package_info.get('summary', u'')

    @property
    def description(self):
        return self.package_info.get('description', u'')

    @property
    def classifiers(self):
        return self.package_info.getlist('classifier')

    @models.permalink
    def get_absolute_url(self):
        return ('djangopypi-release', (), {'package': self.package.name,
                                           'version': self.version})
    
    def delete(self,*args,**kwargs):
        for distribution in self.distributions.all():
            distribution.delete()
        super(Release,self).delete(*args,**kwargs)


class Distribution(models.Model):
    release = models.ForeignKey(Release, related_name="distributions",
                                editable=False)
    content = models.FileField(
        upload_to=lambda i, f: os.path.join(f[:1].lower(), f),
        storage=FileSystemStorage(
            location=settings.DJANGOPYPI_RELEASE_UPLOAD_TO,
            base_url=settings.DJANGOPYPI_RELEASE_URL,
        ),
    )
    md5_digest = models.CharField(max_length=32, blank=True, editable=False)
    filetype = models.CharField(max_length=32, blank=False,
                                choices=conf.DIST_FILE_TYPES)
    pyversion = models.CharField(max_length=16, blank=True,
                                 choices=conf.PYTHON_VERSIONS)
    comment = models.CharField(max_length=255, blank=True)
    signature = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    uploader = models.ForeignKey(User, editable=False)

    @property
    def filename(self):
        return os.path.basename(self.content.name)

    @property
    def display_filetype(self):
        for key,value in conf.DIST_FILE_TYPES:
            if key == self.filetype:
                return value
        return self.filetype

    @property
    def path(self):
        return self.content.name

    def get_absolute_url(self):
        return "%s#md5=%s" % (self.content.url, self.md5_digest)

    class Meta:
        verbose_name = _(u"distribution")
        verbose_name_plural = _(u"distributions")
        unique_together = ("release", "filetype", "pyversion")

    def __unicode__(self):
        return self.filename
    
    def delete(self,*args,**kwargs):
        try:
            self.content.delete()
        except:
            pass
        super(Distribution,self).delete(*args,**kwargs)

class Review(models.Model):
    release = models.ForeignKey(Release, related_name="reviews")
    rating = models.PositiveSmallIntegerField(blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        verbose_name = _(u'release review')
        verbose_name_plural = _(u'release reviews')

@receiver(user_logged_in)
def log_authentication(sender, request, user, *args, **kwargs):
    logger = logging.getLogger('djangopypi.auth_logger')
    logger.info('user: %s authenticated' % user.username)

try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], ["^djangopypi\.models\.PackageInfoField"])
except ImportError:
    pass
