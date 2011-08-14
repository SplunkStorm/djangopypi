import logging

from django.db.models.query import Q
from django.conf import settings
from django.core.urlresolvers import reverse
from django.forms.models import inlineformset_factory
from django.http import Http404, HttpResponseForbidden
from django.views.generic import list_detail, create_update
from django.views.static import serve
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.contrib.auth.views import redirect_to_login

from djangopypi import conf
from djangopypi.decorators import user_maintains_package
from djangopypi.models import Package, Release, Distribution
from djangopypi.http import login_basic_auth, HttpResponseUnauthorized
from djangopypi.forms import ReleaseForm, DistributionUploadForm

def index(request, **kwargs):
    kwargs.setdefault('template_object_name','release')
    kwargs.setdefault(
        'queryset',
        Release.objects.filter(hidden=False).order_by('package__name')
    )
    return list_detail.object_list(request, **kwargs)

def details(request, package, version, simple=False, **kwargs):
    kwargs.setdefault('template_object_name', 'release')
    release = get_object_or_404(Package, name=package).get_release(version)

    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))

    if not simple:
        if not request.user.is_authenticated():
            return redirect_to_login(request.get_full_path())

        kwargs.setdefault('queryset', Release.objects.filter(
            Q(package__download_permissions=None) |
            Q(package__download_permissions__in=request.user.groups.all())
        ))

        try:
            return list_detail.object_detail(request, object_id=release.id,
                                                                    **kwargs)
        except Http404:
            return HttpResponseForbidden('You do not have sufficient \
                                            permissions to view this package.')
    else:
        kwargs.setdefault('queryset', Release.objects.all())
        return list_detail.object_detail(request, object_id=release.id, **kwargs)

def doap(request, package, version, **kwargs):
    kwargs.setdefault('template_name','djangopypi/release_doap.xml')
    kwargs.setdefault('mimetype', 'text/xml')
    return details(request, package, version, **kwargs)

@user_maintains_package()
def manage(request, package, version, **kwargs):
    release = get_object_or_404(Package, name=package).get_release(version)
    
    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))
    
    kwargs['object_id'] = release.pk
    
    kwargs.setdefault('form_class', ReleaseForm)
    kwargs.setdefault('template_name', 'djangopypi/release_manage.html')
    kwargs.setdefault('template_object_name', 'release')
    
    return create_update.update_object(request, **kwargs)

@user_maintains_package()
def manage_metadata(request, package, version, **kwargs):
    kwargs.setdefault('template_name', 'djangopypi/release_manage.html')
    kwargs.setdefault('template_object_name', 'release')
    kwargs.setdefault('extra_context',{})
    kwargs.setdefault('mimetype',settings.DEFAULT_CONTENT_TYPE)
    
    release = get_object_or_404(Package, name=package).get_release(version)
    
    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))
    
    if not release.metadata_version in conf.METADATA_FORMS:
        #TODO: Need to change this to a more meaningful error
        raise Http404('Metadata Version is not supported')
    
    kwargs['extra_context'][kwargs['template_object_name']] = release
    
    form_class = conf.METADATA_FORMS[release.metadata_version]
    if isinstance(form_class, basestring):
        app_module, class_name = form_class.rsplit('.', 1)
        form_class = getattr(__import__(app_module, {}, {}, [class_name]), class_name)
        conf.METADATA_FORMS[release.metadata_version] = form_class
    
    initial = {}
    multivalue = ('classifier',)
    
    for key, values in release.package_info.iterlists():
        if key in multivalue:
            initial[key] = values
        else:
            initial[key] = '\n'.join(values)
    
    if request.method == 'POST':
        form = form_class(data=request.POST, initial=initial)
        
        if form.is_valid():
            for key, value in form.cleaned_data.iteritems():
                if isinstance(value, basestring):
                    release.package_info[key] = value
                elif hasattr(value, '__iter__'):
                    release.package_info.setlist(key, list(value))
            
            release.save()
            return create_update.redirect(kwargs.get('post_save_redirect',None),
                                          release)
    else:
        form = form_class(initial=initial)
    
    kwargs['extra_context']['form'] = form
    
    return render_to_response(kwargs['template_name'], kwargs['extra_context'],
                              context_instance=RequestContext(request),
                              mimetype=kwargs['mimetype'])

@user_maintains_package()
def manage_files(request, package, version, **kwargs):
    release = get_object_or_404(Package, name=package).get_release(version)
    
    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))
    
    kwargs.setdefault('formset_factory_kwargs',{})
    kwargs['formset_factory_kwargs'].setdefault('fields', ('comment',))
    kwargs['formset_factory_kwargs']['extra'] = 0
    
    kwargs.setdefault('formset_factory', inlineformset_factory(Release, Distribution, **kwargs['formset_factory_kwargs']))
    kwargs.setdefault('template_name', 'djangopypi/release_manage_files.html')
    kwargs.setdefault('template_object_name', 'release')
    kwargs.setdefault('extra_context',{})
    kwargs.setdefault('mimetype',settings.DEFAULT_CONTENT_TYPE)
    kwargs['extra_context'][kwargs['template_object_name']] = release
    kwargs.setdefault('formset_kwargs',{})
    kwargs['formset_kwargs']['instance'] = release
    kwargs.setdefault('upload_form_factory', DistributionUploadForm)
    
    if request.method == 'POST':
        formset = kwargs['formset_factory'](data=request.POST,
                                            files=request.FILES,
                                            **kwargs['formset_kwargs'])
        if formset.is_valid():
            formset.save()
            formset = kwargs['formset_factory'](**kwargs['formset_kwargs'])
    else:
        formset = kwargs['formset_factory'](**kwargs['formset_kwargs'])
    
    kwargs['extra_context']['formset'] = formset
    kwargs['extra_context'].setdefault('upload_form',
                                       kwargs['upload_form_factory']())
    
    return render_to_response(kwargs['template_name'], kwargs['extra_context'],
                              context_instance=RequestContext(request),
                              mimetype=kwargs['mimetype'])

@user_maintains_package()
def upload_file(request, package, version, **kwargs):
    release = get_object_or_404(Package, name=package).get_release(version)
    
    if not release:
        raise Http404('Version %s does not exist for %s' % (version,
                                                            package,))
    
    kwargs.setdefault('form_factory', DistributionUploadForm)
    kwargs.setdefault('post_save_redirect', reverse('djangopypi-release-manage-files',
                                                    kwargs={'package': package,
                                                            'version': version}))
    kwargs.setdefault('template_name', 'djangopypi/release_upload_file.html')
    kwargs.setdefault('template_object_name', 'release')
    kwargs.setdefault('extra_context',{})
    kwargs.setdefault('mimetype',settings.DEFAULT_CONTENT_TYPE)
    kwargs['extra_context'][kwargs['template_object_name']] = release
    
    if request.method == 'POST':
        form = kwargs['form_factory'](data=request.POST, files=request.FILES)
        if form.is_valid():
            dist = form.save(commit=False)
            dist.release = release
            dist.uploader = request.user
            dist.save()
            
            return create_update.redirect(kwargs.get('post_save_redirect'),
                                          release)
    else:
        form = kwargs['form_factory']()
    
    kwargs['extra_context']['form'] = form
    
    return render_to_response(kwargs['template_name'], kwargs['extra_context'],
                              context_instance=RequestContext(request),
                              mimetype=kwargs['mimetype'])

def download_dist(request, path, document_root=None, show_indexes=False):
    log = logging.getLogger(__name__)

    can_serve = False
    # Find the related release, and its related package.
    dist = get_object_or_404(Distribution, content=path)
    # Get a list of the groups that can download this package
    package = dist.release.package
    download_permissions = package.download_permissions.all()
    username = 'Anonymous'

    if download_permissions.count() == 0:
        # If no download permissions, anon users can access the package
        can_serve = True
    else:
        # Check authentication, falling-back to basic auth if necessary
        if request.user.is_authenticated():
            user = request.user
        else:
            user = login_basic_auth(request)

        if user is None:
            return HttpResponseUnauthorized('pypi')
        else:
            # If authenticated, check that the user's primary group is
            # in the package's download_permissions
            user_groups = user.groups.all()
            if len(user_groups) > 0:
                if user_groups[0] in download_permissions:
                    username = user.username
                    can_serve = True

    if can_serve:
        log.info('user: %s package: %s downloaded' % (username, package.name))
        return serve(request, path, document_root, show_indexes)
    else:
        log.info('user: %s package: %s download permission denied' % (
            username, package.name
        ))
        return HttpResponseForbidden(
            'You are not authorised to download %s' % package.name
        )
