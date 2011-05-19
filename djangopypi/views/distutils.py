import os

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponseBadRequest, \
                        HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.utils.datastructures import MultiValueDict

from djangopypi import conf
from djangopypi.decorators import basic_auth
from djangopypi.forms import PackageForm, ReleaseForm
from djangopypi.models import Package, Release, Distribution, Classifier

from datetime import datetime

import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)

ALREADY_EXISTS_FMT = _(
    "A file named '%s' already exists for %s. Please create a new release.")

def submit_package_or_release(user, post_data, files):
    """Registers/updates a package or release"""
    try:
        package = Package.objects.get(name=post_data['name'])
        if not (conf.GLOBAL_OWNERSHIP or user in package.owners.all()):
            return HttpResponseForbidden(
                    "That package is owned by someone else!")
    except Package.DoesNotExist:
        package = None

    package_form = PackageForm(post_data, instance=package)
    if package_form.is_valid():
        package = package_form.save(commit=False)
        package.owner = user
        package.save()
        for c in post_data.getlist('classifiers'):
            classifier, created = Classifier.objects.get_or_create(name=c)
            package.classifiers.add(classifier)
        if files:
            allow_overwrite = getattr(settings,
                "DJANGOPYPI_ALLOW_VERSION_OVERWRITE", False)
            try:
                release = Release.objects.get(version=post_data['version'],
                                              package=package,
                                              distribution=settings.DJANGOPYPI_RELEASE_UPLOAD_TO + '/' +
                                              files['distribution']._name)
                if not allow_overwrite:
                    return HttpResponseForbidden(ALREADY_EXISTS_FMT % (
                                release.filename, release))
            except Release.DoesNotExist:
                release = None

            # If the old file already exists, django will append a _ after the
            # filename, however with .tar.gz files django does the "wrong"
            # thing and saves it as package-0.1.2.tar_.gz. So remove it before
            # django sees anything.
            release_form = ReleaseForm(post_data, files, instance=release)
            if release_form.is_valid():
                if release and os.path.exists(release.distribution.path):
                    os.remove(release.distribution.path)
                release = release_form.save(commit=False)
                release.package = package
                release.save()
            else:
                return HttpResponseBadRequest(
                        "ERRORS: %s" % release_form.errors)
    else:
        return HttpResponseBadRequest("ERRORS: %s" % package_form.errors)

    return HttpResponse()

@basic_auth
@transaction.autocommit
def register_or_upload(request):

    username = request.user.username
    
    if request.method != 'POST':
        logger.info('Only post requests are supported. User %s' % (username))
        return HttpResponseBadRequest('Only post requests are supported.')

    name = request.POST.get('name',None).strip()
    
    
    if not name:
        logger.info('No package name specified. User %s' % (username))
        return HttpResponseBadRequest('No package name specified.')

    # get group of user
    try:
        group = request.user.groups.get()
    except:
        logger.info('%s is in more than 1 group, not allowing package to be uploaded.' % (username))
        return HttpResponseForbidden('%s is in more than 1 group, not allowing package to be uploaded.' % (username))
        
    if not group:
        logger.info('%s is not in a group, not allowing package to be uploaded.' % (username))
        return HttpResponseForbidden('%s is not in a group, not allowing package to be uploaded.' % (username))

    # check group can upload
    if not 'add_package' in [ perm.codename for perm in group.permissions.all()]:
        logger.info("%s's group - %s does not have permissions to upload new packages." % (username, group.name))
        return HttpResponseForbidden("%s's group - %s does not have permissions to upload new packages." % (username, group.name))
    
    # fetch existing package or create new one
    try:
        package = Package.objects.get(name=name)
    except Package.DoesNotExist:
        package = Package.objects.create(name=name)
        package.owners.add(request.user.groups.all()[0])
        
    if not request.user.is_superuser:
        if group != package.owners.get():
            logger.info("'%s' is in the group '%s', only members of '%s' can upload new versions of this package." % (username, package.owners.get().name, group.name))
            return HttpResponseForbidden("'%s' is in the group '%s', only members of '%s' can upload new versions of this package." % (username, package.owners.get().name, group.name))
    
    version = request.POST.get('version', None)
    if version:
        version = version.strip()
    
    # check if package with version number already exists, error if true
    if not Release.objects.filter(package=package,version=version):
        release, created = Release.objects.get_or_create(package=package,
                                                         version=version)
    
        metadata_version = request.POST.get('metadata_version', None)
        if not metadata_version:
            metadata_version = release.metadata_version
    
        if metadata_version:
            metadata_version = metadata_version.strip()
        
        if not version or not metadata_version:
            transaction.rollback()
            logger.info('Release version and metadata version must be specified. User %s' %(username))
            return HttpResponseBadRequest('Release version and metadata version must be specified')
        
        if not metadata_version in conf.METADATA_FIELDS:
            transaction.rollback()
            logger.info('Metadata version must be one of: %s. %s' 
                                          (', '.join(conf.METADATA_FIELDS.keys()),), username)
            return HttpResponseBadRequest('Metadata version must be one of: %s' 
                                          (', '.join(conf.METADATA_FIELDS.keys()),))
        
        
        if (('classifiers' in request.POST or 'download_url' in request.POST) and 
            metadata_version == '1.0'):
            metadata_version = '1.1'
        
        release.metadata_version = metadata_version
        
        fields = conf.METADATA_FIELDS[metadata_version]
        
        if 'classifiers' in request.POST:
            request.POST.setlist('classifier',request.POST.getlist('classifiers'))
        
        release.package_info = MultiValueDict(dict(filter(lambda t: t[0] in fields,
                                                          request.POST.iterlists())))
        
        for key, value in release.package_info.iterlists():
            release.package_info.setlist(key,
                                         filter(lambda v: v != 'UNKNOWN', value))
        
        release.save()
        if not 'content' in request.FILES:
            transaction.commit()
            logger.info('release registered for package %s %s, uploaded by user %s at time %s' % (package.name, version, request.user, datetime.now()))
            return HttpResponse('release registered')
        
        uploaded = request.FILES.get('content')
        
        for dist in release.distributions.all():
            if os.path.basename(dist.content.name) == uploaded.name:
                """ Need to add handling optionally deleting old and putting up new """
                transaction.rollback()
                logger.info('That file has already been uploaded... User %s' % (username))
                return HttpResponseBadRequest('That file has already been uploaded...')
    
        md5_digest = request.POST.get('md5_digest','')
        
        try:
            new_file = Distribution.objects.create(release=release,
                                                   content=uploaded,
                                                   filetype=request.POST.get('filetype','sdist'),
                                                   pyversion=request.POST.get('pyversion',''),
                                                   uploader=request.user,
                                                   comment=request.POST.get('comment',''),
                                                   signature=request.POST.get('gpg_signature',''),
                                                   md5_digest=md5_digest)
        except Exception, e:
            transaction.rollback()
            print str(e)
        
        transaction.commit()
        logger.info('package %s %s, uploaded by user %s at %s' % (package.name, version, username, datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')))
        return HttpResponse('upload accepted')
    
    else:
        logger.info('Package %s with version number %s already exists. User %s' % (name, version, username))
        return HttpResponseForbidden('Package %s with version number %s already exists.' % (name, version))


def list_classifiers(request, mimetype='text/plain'):
    response = HttpResponse(mimetype=mimetype)
    response.write(u'\n'.join(map(lambda c: c.name,Classifier.objects.all())))
    return response

