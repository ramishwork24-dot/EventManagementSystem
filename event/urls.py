from django.urls import path
from . import views

#URL routing configurtion of views
urlpatterns = [
    path('', views.EventListView.as_view(), name='event_home'),
    path('event/create/', views.EventCreateView.as_view(), name='event_create'),
    path('event/<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    path('event/<int:pk>/edit/', views.EventUpdateView.as_view(), name='event_update'),

    path('event/<int:pk>/book/', views.BookingCreateView.as_view(), name='booking_create'),
    path('event/<int:pk>/confirmation/', views.BookingConfirmationView.as_view(), name='booking_confirmation'),
    path('my-bookings/', views.UserBookingListView.as_view(), name='user_booking_list'),

    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'),
]