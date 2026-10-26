from django.contrib import admin

from .models import Category, Post, Topic


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "created_at"]
    search_fields = ["name"]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "category", "owner", "created_at"]
    search_fields = ["title"]
    list_filter = ["category"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["id", "topic", "owner", "created_at"]
    search_fields = ["text"]
