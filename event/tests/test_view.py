from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from decimal import Decimal

from event.models import Event, Ticket, Booking, BookingItem

now = timezone.now()

#Creating in-memory template loaders so tests do not need physical .html files
TEST_TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': False,
    'OPTIONS': {
        'loaders': [
            ('django.template.loaders.locmem.Loader', {
                'event/event_home.html': '{% block content %}{% endblock %}',
                'event/event_detail.html': '{% block content %}{% endblock %}',
                'event/event_form.html': '{% block content %}{% endblock %}',
                'event/booking_confirmation.html': '{% block content %}{% endblock %}',
                'event/user_booking_list.html': '{% block content %}{% endblock %}',
            }),
        ]
    }
}]


#EventListView Tests
#Overriding settings to use the above mock templates
@override_settings(TEMPLATES=TEST_TEMPLATES)
class EventListViewTest(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user('test user', 'user@test.com', 'password123')
        #Past Event (to test if it gets filtered out)
        Event.objects.create(
            organizer = self.test_user, title = 'past test title', location = 'test location',
            start_time = now - timedelta(days=2), end_time = now - timedelta(days=1), capacity = 30
        )
        #Future events (mutiple to test ordering and pagination)
        self.future_events = []
        for i in range(7):
            e = Event.objects.create(
                organizer = self.test_user, title = f'test title {i}', location = 'test location',
                start_time = now + timedelta(days=i+1), end_time = now + timedelta(days=i+1, hours=2),
                capacity = 100
            )
            Ticket.objects.create(event = e, tier_name = 'test tier', price = Decimal('20.00'),
                quantity_available = 50,
            )
            self.future_events.append(e)

    def test_list_view_filtering_ordering_pagination_and_queries(self):
        response = self.client.get(reverse('event_home'))
        self.assertEqual(response.status_code, 200)
        #Filtering and pagination test
        events_in_context = list(response.context['events'])
        self.assertEqual(len(events_in_context), 6)
        self.assertNotIn('past test title', [e.title for e in events_in_context])
        #Ordering check
        self.assertEqual(events_in_context[0], self.future_events[0])
        self.assertEqual(events_in_context[1], self.future_events[1])
        #Query Optimization check
        with self.assertNumQueries(0):
            for event in response.context['events']:
                list(event.tickets.all())

#EventDetailView Tests
@override_settings(TEMPLATES=TEST_TEMPLATES)
class EventDetailViewTest(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user('test user', 'user@test.com', 'password123')
        self.test_event = Event.objects.create(
            organizer=self.test_user, title='test event', location='test location',
            start_time=now + timedelta(days=1), end_time=now + timedelta(days=1, hours=2), capacity=100
        )
        self.ticket = Ticket.objects.create(
            event=self.test_event, tier_name='VIP', price=Decimal('50.00'), quantity_available=20
        )

    def test_detail_view_context_form_and_query_optimization(self):
        response = self.client.get(reverse('event_detail', kwargs={'pk':self.test_event.pk}))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['event'], self.test_event)
        self.assertIn('form', response.context)
        self.assertIn(f'ticket_{self.ticket.id}', response.context['form'].fields)

        with self.assertNumQueries(0):
            list(response.context['event'].tickets.all())

#EventCreateView Tests
@override_settings(TEMPLATES=TEST_TEMPLATES)
class EventCreateViewTest(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user('organizer', 'org@test.com', 'password123')

    def test_unauthenticated_guard(self):
        #unauthorized user
        response = self.client.get(reverse('event_create'))
        self.assertEqual(response.status_code, 302)

        #authenticated user
        self.client.force_login(self.test_user)
        response = self.client.get(reverse('event_create'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('ticket_formset', response.context)

    def test_successful_atmoic_creation(self):
        self.client.force_login(self.test_user)
        post_data = {
            'title': 'test title',
            'description': 'testing purposes only',
            'location': 'test location',
            'start_time': (now +timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_time': (now + timedelta(days=1, hours=3)).strftime('%Y-%m-%dT%H:%M'),
            'capacity': 100,
            #management and form data
            'tickets-TOTAL_FORMS': '1',
            'tickets-INITIAL_FORMS': '0',
            'tickets-MIN_NUM_FORMS': '1',
            'tickets-MAX_NUM_FORMS': '1000',
            'tickets-0-tier_name': 'Early Bird',
            'tickets-0-price': '25.00',
            'tickets-0-quantity_available': '30',
        }
        response = self.client.post(reverse('event_create'), post_data)
        #tests
        self.assertEqual(response.status_code, 302)
        created_event = Event.objects.get(title='test title')
        self.assertEqual(created_event.organizer, self.test_user)
        self.assertEqual(created_event.tickets.count(), 1)

#EventUpdateView tests
@override_settings(TEMPLATES=TEST_TEMPLATES)
class EventUpdateViewTest(TestCase):
    def setUp(self):
        self.test_user = User.objects.create_user('test user', 'user@test.com', 'password123')
        self.test_event = Event.objects.create(
            organizer=self.test_user, title='test event', location='test location',
            start_time=now + timedelta(days=1), end_time=now + timedelta(days=1, hours=2), capacity=100
        )
        self.ticket = Ticket.objects.create(
            event=self.test_event, tier_name='VIP', price=Decimal('50.00'), quantity_available=20
        )
        #intruder
        self.intruder = User.objects.create_user('intruder', 'intruder@test.com', 'password321')

    def test_authorization_guard_and_update_inventory_guard(self):
        #not letting intruder access someone else's data
        self.client.force_login(self.intruder)
        response = self.client.get(reverse('event_update', kwargs={'pk': self.test_event.pk}))
        self.assertEqual(response.status_code, 403)

        #Original author updating the data
        self.client.force_login(self.test_user)
        post_data = {
            'title': 'Updated Title',
            'description': 'Description',
            'location': 'Venue',
            'start_time': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_time': (now + timedelta(days=1, hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'capacity': 100,
            'tickets-TOTAL_FORMS': '1',
            'tickets-INITIAL_FORMS': '1',
            'tickets-MIN_NUM_FORMS': '1',
            'tickets-MAX_NUM_FORMS': '1000',
            'tickets-0-id': self.ticket.id,
            'tickets-0-tier_name': 'VIP',
            'tickets-0-price': '50.00',
            'tickets-0-quantity_available': '25',
        }
        response = self.client.post(reverse('event_update', kwargs={'pk': self.test_event.pk}), post_data)
        self.assertEqual(response.status_code, 302)

        self.test_event.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.test_event.title, 'Updated Title')
        self.assertEqual(self.ticket.quantity_available, 25)

#BookingCreateView tests
@override_settings(TEMPLATES=TEST_TEMPLATES)
class BookingCreateViewTest(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user('organizer', 'org@test.com', 'password123')
        self.customer = User.objects.create_user('customer', 'cust@test.com', 'password123')
        self.event = Event.objects.create(
            organizer=self.organizer, title='Booking Event', location='Venue',
            start_time=now + timedelta(days=1), end_time=now + timedelta(days=1, hours=2), capacity=50
        )
        self.ticket = Ticket.objects.create(
            event=self.event, tier_name='Standard', price=Decimal('20.00'), quantity_available=10
        )

    def test_successful_booking_creation_and_inventory_deduction(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('booking_create', kwargs={'pk': self.event.pk}),
            {f'ticket_{self.ticket.id}': '2'}
        )

        booking = Booking.objects.get(user=self.customer, event=self.event)
        self.assertRedirects(response, reverse('booking_confirmation', kwargs={'pk': booking.pk}))

        self.assertEqual(booking.total_price, Decimal('40.00'))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.quantity_available, 8)

    def test_stock_exceeded_error(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('booking_create', kwargs={'pk': self.event.pk}),
            {f'ticket_{self.ticket.id}': '15'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 0)

#BookingConfimationView tests
@override_settings(TEMPLATES=TEST_TEMPLATES)
class BookingConfirmationViewTest(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user('organizer', 'org@test.com', 'password123')
        self.user1 = User.objects.create_user('user1', 'u1@test.com', 'password123')
        self.user2 = User.objects.create_user('user2', 'u2@test.com', 'password123')
        
        self.event = Event.objects.create(
            organizer=self.organizer, title='Event', location='Venue',
            start_time=now + timedelta(days=1), end_time=now + timedelta(days=1, hours=2), capacity=50
        )
        self.ticket = Ticket.objects.create(
            event=self.event, tier_name='Standard', price=Decimal('20.00'), quantity_available=10
        )
        self.booking = Booking.objects.create(user=self.user1, event=self.event, total_price=Decimal('20.00'))
        BookingItem.objects.create(booking=self.booking, ticket=self.ticket, quantity=1, price_at_purchase=Decimal('20.00'))

    def test_booking_confirmation_isolation_and_queries(self):
        #Catching intruder
        self.client.force_login(self.user2)
        response = self.client.get(reverse('booking_confirmation', kwargs={'pk': self.booking.pk}))
        self.assertEqual(response.status_code, 404)
        #original buyer
        self.client.force_login(self.user1)
        response = self.client.get(reverse('booking_confirmation', kwargs={'pk': self.booking.pk}))
        self.assertEqual(response.status_code, 200)

        with self.assertNumQueries(0):
            booking_obj = response.context['booking']
            _ = booking_obj.event.title
            _ = list(booking_obj.items.all())

    def test_user_booking_list_isolation(self):
                self.client.force_login(self.user1)
                response = self.client.get(reverse('user_booking_list'))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.context['bookings']), 1)
                self.assertEqual(response.context['bookings'][0], self.booking)
                