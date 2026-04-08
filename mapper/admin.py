from django.contrib import admin
from .models import Project, Task, Link


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0


class LinkInline(admin.TabularInline):
    model = Link
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'owner')
    inlines = [TaskInline, LinkInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'task_id', 'duration', 'delay', 'project')
    list_filter = ('project',)


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = ('source_task_id', 'target_task_id', 'project')
    list_filter = ('project',)
