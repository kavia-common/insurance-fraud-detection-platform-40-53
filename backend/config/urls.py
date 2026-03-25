"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

API_TAGS = [
    {'name': 'health', 'description': 'Service health checks'},
    {'name': 'ingestion', 'description': 'Claim ingestion endpoints'},
    {'name': 'claims', 'description': 'Claim browsing and detail'},
    {'name': 'rules', 'description': 'Rules configuration (CRUD)'},
    {'name': 'scoring', 'description': 'Rules-based scoring operations'},
    {'name': 'queue', 'description': 'Investigation queue views'},
    {'name': 'investigators', 'description': 'Investigator directory'},
    {'name': 'cases', 'description': 'Case management'},
    {'name': 'assignments', 'description': 'Claim assignments to investigators'},
    {'name': 'relationships', 'description': 'Network/relationship graph building blocks'},
    {'name': 'outcomes', 'description': 'Investigation outcomes'},
    {'name': 'analytics', 'description': 'Analytics for dashboards'},
]
schema_view = get_schema_view(
   openapi.Info(
      title="Insurance Fraud Detection API",
      default_version='v1',
      description="Backend API for claim ingestion, rules-based scoring, investigator queue, assignments/cases, network relationships, outcomes, and analytics.",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   tags=API_TAGS,
)

def get_full_url(request):
    scheme = request.scheme
    host = request.get_host()
    forwarded_port = request.META.get("HTTP_X_FORWARDED_PORT")

    if ':' not in host and forwarded_port:
        host = f"{host}:{forwarded_port}"

    return f"{scheme}://{host}"

@csrf_exempt
def dynamic_schema_view(request, *args, **kwargs):
    url = get_full_url(request)
    view = get_schema_view(
        openapi.Info(
            title="Insurance Fraud Detection API",
            default_version='v1',
            description="Backend API for claim ingestion, rules-based scoring, investigator queue, assignments/cases, network relationships, outcomes, and analytics.",
        ),
        public=True,
        url=url,
        patterns=urlpatterns,
    )
    return view.with_ui('swagger', cache_timeout=0)(request)

urlpatterns += [
    re_path(r'^docs/$', dynamic_schema_view, name='schema-swagger-ui'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    re_path(r'^swagger\.json$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
]