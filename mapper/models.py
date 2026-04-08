from django.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    name = models.CharField(max_length=200, default="Default Project")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class Task(models.Model):
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.CASCADE)
    task_id = models.CharField(max_length=50, help_text="Client-side unique ID")
    name = models.CharField(max_length=200)
    duration = models.IntegerField(default=10)
    delay = models.IntegerField(default=0)
    timestamp = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (delay: {self.delay}d)"

    class Meta:
        ordering = ['created_at']


class Link(models.Model):
    project = models.ForeignKey(Project, related_name='links', on_delete=models.CASCADE)
    source_task_id = models.CharField(max_length=50)
    target_task_id = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.source_task_id} → {self.target_task_id}"

    class Meta:
        unique_together = ('project', 'source_task_id', 'target_task_id')
