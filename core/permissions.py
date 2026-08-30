from rest_framework.permissions import BasePermission
def app_role(user):
    if not user or not user.is_authenticated: return None
    if user.is_superuser or user.is_staff: return 'admin'
    try: return user.profile.role
    except Exception: return None
class IsProfessorOrAdmin(BasePermission):
    def has_permission(self, request, view): return app_role(request.user) in ('professor','admin')
class IsStudentOrAdmin(BasePermission):
    def has_permission(self, request, view): return app_role(request.user) in ('student','admin')
