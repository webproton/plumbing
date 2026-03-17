from rest_framework import viewsets, permissions, mixins, filters,status

class IsReviewOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.reviewer == request.user
