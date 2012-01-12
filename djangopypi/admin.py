from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from djangopypi.models import Package, Release, Classifier, \
                              Distribution, Review

def full_delete_selected(self,request,queryset):
    for obj in queryset:
        obj.delete()

    self.message_user(request, "%s rows were successfully deleted" % queryset.count())
full_delete_selected.short_description = "Delete selected entries"

admin.site.add_action(full_delete_selected)

def make_anonymous(modeladmin, request, queryset):
    for obj in queryset:
        if isinstance(obj, Package):
            obj.download_permissions.clear()
    modeladmin.message_user(request, "Made %s packages anonymous" % queryset.count())
make_anonymous.short_description = "Make packages anonymous"

def available_to_authed_users(modeladmin, request, queryset):
    for obj in queryset:
        if isinstance(obj, Package):
            obj.download_permissions.clear()
            for group in Group.objects.all():
                if not group in obj.download_permissions.all():
                    obj.download_permissions.add(group)
    modeladmin.message_user(request,
        "Made %s packages available only to authenticated users." % (
            queryset.count()
    ))
available_to_authed_users.short_description = "Make packages available only " \
                                              "to authenticated users"

class FullDeletingModelAdmin(admin.ModelAdmin):
    actions = ['full_delete_selected']
    def get_actions(self, request):
        actions = super(FullDeletingModelAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions

class PackageModelAdmin(FullDeletingModelAdmin):
    actions = [
        make_anonymous,
        available_to_authed_users,
    ]
    list_display = (
        'name',
    )
    search_fields = ('name',)

def make_staff(modeladmin, request, queryset):
    count = 0
    for obj in queryset:
        if isinstance(obj, User):
            obj.is_staff = True
            obj.save()
            count += 1
    modeladmin.message_user(request, "Made %d users staff" % count)

## Following only valid in Django 1.4
#class GroupFilter(SimpleListFilter):
#    title = 'Primary Group'
#    parameter_name = 'primary_group'
#
#    def lookups(self, request, model_admin):
#        return [(group.name, group.id) for group in Group.objects.all()]
#
#    def queryset(self, request, queryset):
#        try:
#            group = Group.objects.get(self.value)
#            group_id = group.id
#        except Group.DoesNotExist:
#            group_id = None
#
#        return queryset.filter(groups__id=group_id)
#

class EnhancedUserAdmin(UserAdmin):
    # list_filter = UserAdmin.list_filter + (GroupFilter,)

    actions = [make_staff,]

admin.site.unregister(User)
admin.site.register(User, EnhancedUserAdmin)

admin.site.register(Package,PackageModelAdmin)
admin.site.register(Release,FullDeletingModelAdmin)
admin.site.register(Classifier)
admin.site.register(Distribution,FullDeletingModelAdmin)
admin.site.register(Review)
