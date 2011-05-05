from django.contrib import admin
from djangopypi.models import Package, Release, Classifier, \
                              Distribution, Review

def full_delete_selected(self,request,queryset):
    for obj in queryset:
        obj.delete()
        self.message_user(request, "%s rows were successfully deleted" % queryset.count())
full_delete_selected.short_description = "Delete selected entries"

admin.site.add_action(full_delete_selected)

class FullDeletingModelAdmin(admin.ModelAdmin):
    actions = ['full_delete_selected']
    def get_actions(self, request):
        actions = super(FullDeletingModelAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions

admin.site.register(Package,FullDeletingModelAdmin)
admin.site.register(Release,FullDeletingModelAdmin)
admin.site.register(Classifier)
admin.site.register(Distribution,FullDeletingModelAdmin)
admin.site.register(Review)
