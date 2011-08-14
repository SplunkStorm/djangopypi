from django.contrib import admin
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

class FullDeletingModelAdmin(admin.ModelAdmin):
    actions = ['full_delete_selected']
    def get_actions(self, request):
        actions = super(FullDeletingModelAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions

class PackageModelAdmin(FullDeletingModelAdmin):
    actions = [make_anonymous]

admin.site.register(Package,PackageModelAdmin)
admin.site.register(Release,FullDeletingModelAdmin)
admin.site.register(Classifier)
admin.site.register(Distribution,FullDeletingModelAdmin)
admin.site.register(Review)
