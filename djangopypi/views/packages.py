from django.conf import settings
from django.db.models.query import Q
from django.http import Http404, HttpResponseRedirect, HttpResponseForbidden
from django.forms.models import inlineformset_factory
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.views.generic import list_detail, create_update
from django.contrib.auth.views import redirect_to_login

from djangopypi import conf
from djangopypi.http import login_basic_auth, HttpResponseUnauthorized
from djangopypi.decorators import user_owns_package, user_maintains_package
from djangopypi.models import Package, Release
from djangopypi.forms import SimplePackageSearchForm, PackageForm

def user_packages(user):
    ''' Return a list of packages that the user has permission to download '''
    if user.is_superuser:
        return Package.objects.all()
    else:
        return Package.objects.filter(
            Q(download_permissions=None) |
            Q(allow_authenticated=True) |
            Q(download_permissions__in=user.groups.all())
        ).distinct()

def index(request, **kwargs):
    kwargs.setdefault('template_object_name', 'package')
    kwargs.setdefault('queryset', Package.objects.all())
    return list_detail.object_list(request, **kwargs)

def simple_index(request, **kwargs):
    if request.user.is_authenticated():
        user = request.user
    else:
        user = login_basic_auth(request)

    if user is None:
        return HttpResponseUnauthorized('pypi')

    kwargs.setdefault('template_name', 'djangopypi/package_list_simple.html')
    kwargs['queryset'] = user_packages(user)
    return index(request, **kwargs)

def details(request, package, simple=False, **kwargs):
    package = get_object_or_404(Package, name=package)
    kwargs.setdefault('template_object_name', 'package')

    if not simple:
        if not request.user.is_authenticated():
            return redirect_to_login(request.get_full_path())
        else:
            user = request.user
    else:
        user = login_basic_auth(request)
        if not user:
            return HttpResponseUnauthorized('pypi')

    kwargs.setdefault('queryset', user_packages(user))

    try:
        return list_detail.object_detail(request, object_id=package, **kwargs)
    except Http404:
        return HttpResponseForbidden('You do not have sufficient \
                                      permissions to view this package')

def simple_details(request, package, **kwargs):
    kwargs.setdefault('template_name', 'djangopypi/package_detail_simple.html')
    try:
        return details(request, package, simple=True, **kwargs)
    except Http404, e:
        if conf.PROXY_MISSING:
            return HttpResponseRedirect('%s/%s/' % 
                                        (conf.PROXY_BASE_URL.rstrip('/'),
                                         package))
        raise e

def doap(request, package, **kwargs):
    kwargs.setdefault('template_name', 'djangopypi/package_doap.xml')
    kwargs.setdefault('mimetype', 'text/xml')
    return details(request, package, simple=True, **kwargs)

def search(request, **kwargs):
    if request.method == 'POST':
        form = SimplePackageSearchForm(request.POST)
    else:
        form = SimplePackageSearchForm(request.GET)
    
    if form.is_valid():
        q = form.cleaned_data['q']
        kwargs['queryset'] = Package.objects.filter(Q(name__contains=q) | 
                                                    Q(releases__package_info__contains=q)).distinct()

    return index(request, **kwargs)

@user_owns_package()
def manage(request, package, **kwargs):
    kwargs['object_id'] = package
    kwargs.setdefault('form_class', PackageForm)
    kwargs.setdefault('template_name', 'djangopypi/package_manage.html')
    kwargs.setdefault('template_object_name', 'package')

    return create_update.update_object(request, **kwargs)

@user_maintains_package()
def manage_versions(request, package, **kwargs):
    package = get_object_or_404(Package, name=package)
    kwargs.setdefault('formset_factory_kwargs', {})
    kwargs['formset_factory_kwargs'].setdefault('fields', ('hidden',))
    kwargs['formset_factory_kwargs']['extra'] = 0

    kwargs.setdefault('formset_factory', inlineformset_factory(Package, Release, **kwargs['formset_factory_kwargs']))
    kwargs.setdefault('template_name', 'djangopypi/package_manage_versions.html')
    kwargs.setdefault('template_object_name', 'package')
    kwargs.setdefault('extra_context',{})
    kwargs.setdefault('mimetype',settings.DEFAULT_CONTENT_TYPE)
    kwargs['extra_context'][kwargs['template_object_name']] = package
    kwargs.setdefault('formset_kwargs',{})
    kwargs['formset_kwargs']['instance'] = package

    if request.method == 'POST':
        formset = kwargs['formset_factory'](data=request.POST, **kwargs['formset_kwargs'])
        if formset.is_valid():
            formset.save()
            return create_update.redirect(kwargs.get('post_save_redirect', None),
                                          package)

    formset = kwargs['formset_factory'](**kwargs['formset_kwargs'])

    kwargs['extra_context']['formset'] = formset

    return render_to_response(kwargs['template_name'], kwargs['extra_context'],
                              context_instance=RequestContext(request),
                              mimetype=kwargs['mimetype'])
