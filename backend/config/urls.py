from django.urls import path
from routing.views import plan_route, geocode

urlpatterns = [
    path('api/plan/', plan_route, name='plan'),
    path('api/geocode/', geocode, name='geocode'),
]
