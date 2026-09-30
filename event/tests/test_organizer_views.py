from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from event.models import Event, Ticket, Booking, BookingItem

User = get_user_model()


class OrganizerViewTests(TestCase):
    def setUp(self):
        #Users
        self.organizer = User.objects.create_user(username='organizer', password='password123')
        self.other_organizer = User.objects.create_user(username='other_org', password='password321')
        self.customer = User.objects.create_user(username='customer', password='password098')

        #Events
        self.event = Event.objects.create(
            title = 'Test Event 1',
            description = 'Test Purposes Only',
            location = 'Test location',
            start_time = timezone.now() + timedelta(days=2),
            end_time = timezone.now() + timedelta(days=3),
            capacity = 100,
            organizer = self.organizer
        )
        self.other_event = Event.objects.create(
            title = 'Test Event 2',
            description = 'Test Purposes Only',
            location = 'Test location',
            start_time = timezone.now() + timedelta(days=4),
            end_time = timezone.now() + timedelta(days=5),
            capacity = 500,
            organizer = self.other_organizer
        )

        #Ticket Tier
        self.ticket = Ticket.objects.create(
            event = self.event,
            tier_name = 'Test Tier',
            price = 50.00,
            quantity_available = 8,
        )

        #Booking
        self.booking = Booking.objects.create(
            user = self.customer,
            event = self.event,
            status = Booking.Status.PENDING,
            total_price = 100.00,
        )
        self.booking_item = BookingItem.objects.create(
            booking = self.booking,
            ticket = self.ticket,
            quantity = 2,
            price_at_purchase = 50.00,
        )

        #URLs
        self.dashboard_url = reverse('organizer_dashboard')
        self.approve_url = reverse('booking_approve', kwargs={'pk':self.booking.pk})
        self.cancel_url = reverse('booking_cancel', kwargs={'pk': self.booking.pk})

# =========================================================================
# 1. ORGANIZER DASHBOARD TESTS
# =========================================================================
    
    def test_dashboard_unauthenticated_redirects_to_login(self):
        response = self.client.get(self.dashboard_url)
        self.assertRedirects(response, f'/login/?next={self.dashboard_url}')

    def test_dashboard_queries_scoped_to_logged_in_organizer(self):
        self.client.login(username='organizer', password='password123')
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        events = response.context['events']
        self.assertIn(self.event, events)
        self.assertNotIn(self.other_event, events)

# =========================================================================
# 2. BOOKING APPROVAL TESTS
# =========================================================================

    def test_approve_booking_unauthenticated_redirects(self):
        response = self.client.post(self.approve_url)
        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.PENDING)

    def test_approve_booking_unauthorized_user_forbidden(self):
        self.client.login(username='customer', password='password098')
        response = self.client.post(self.approve_url)

        self.assertEqual(response.status_code, 403)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.PENDING)

    def test_approve_booking_success(self):
        self.client.login(username='organizer', password='password123')
        response = self.client.post(self.approve_url)

        self.assertRedirects(response, self.dashboard_url)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)

# =========================================================================
# 3. BOOKING CANCELLATION & INVENTORY RESTORATION TESTS
# =========================================================================

    def test_cancel_booking_unauthorized_user_forbidden(self):
        self.client.login(username='customer', password='password098')
        response = self.client.post(self.cancel_url)

        self.assertEqual(response.status_code, 403)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.PENDING)

    def test_cancel_booking_restore_ticket_stock(self):
        self.client.login(username='organizer', password='password123')
        initial_stock = self.ticket.quantity_available

        response = self.client.post(self.cancel_url)

        self.assertRedirects(response, self.dashboard_url)
        self.booking.refresh_from_db()
        self.ticket.refresh_from_db()

        self.assertEqual(self.booking.status, Booking.Status.CANCELLED)
        self.assertEqual(
            self.ticket.quantity_available,
            initial_stock + self.booking_item.quantity
        )

    def test_cancel_already_cancelled_booking_idempotency(self):
        self.booking.status = Booking.Status.CANCELLED
        self.booking.save()

        self.client.login(username='organizer', password='password123')
        initial_stock = self.ticket.quantity_available

        response = self.client.post(self.cancel_url)

        self.assertRedirects(response, self.dashboard_url)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.quantity_available, initial_stock)