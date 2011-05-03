from django.http import HttpResponseNotAllowed

from djangopypi import conf
from djangopypi.decorators import csrf_exempt
from djangopypi.http import parse_distutils_request
from djangopypi.views.xmlrpc import parse_xmlrpc_request

@csrf_exempt
def root(request, fallback_view=None, **kwargs):
    """ Root view of the package index, handle incoming actions from distutils
    or redirect to a more user friendly view """

    if request.method == 'POST':
        if request.META['CONTENT_TYPE'] == 'text/xml':
            return parse_xmlrpc_request(request)
        parse_distutils_request(request)
        action = request.POST.get(':action','')
    else:
        action = request.GET.get(':action','')
    
    if not action:
        if fallback_view is None:
            fallback_view = conf.FALLBACK_VIEW
            if isinstance(fallback_view, basestring):
                module, func_name = fallback_view.rsplit('.', 1)
                fallback_view = getattr(__import__(module, {}, {}, [func_name]), func_name)
                conf.FALLBACK_VIEW = fallback_view
        return fallback_view(request, **kwargs)
    
    if not action in conf.ACTION_VIEWS:
        print 'unknown action: %s' % (action,)
        return HttpResponseNotAllowed(conf.ACTION_VIEW.keys())
    
    view_func = conf.ACTION_VIEWS[action]
    if isinstance(view_func, basestring):
        module, func_name = view_func.rsplit('.', 1)
        view_func = getattr(__import__(module, {}, {}, [func_name]), func_name)
        conf.ACTION_VIEWS[action] = view_func
    
    return view_func(request, **kwargs)
