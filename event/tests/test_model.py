from event.models import Event, Ticket, Booking, BookingItem
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.core.files.uploadedfile import SimpleUploadedFile
import shutil
import tempfile
now = timezone.now()
TEMP_MEDIA_DIR = tempfile.mkdtemp()


#Tests For Models

#'Event' Tests
@override_settings(MEDIA_ROOT=TEMP_MEDIA_DIR)
class EventModelTest(TestCase):
    def test_successful_save_and_representation(self):
        #Set Up
        test_event = Event.objects.create(
            title = 'Test Title',
            description = 'Testing Purposes Only',
            location = 'Test location',
            start_time = now + timedelta(days=1),
            end_time = now + timedelta(days=1, hours=3),
            capacity = 100
        )
        #Test
        #Assert that the data was saved to the database
        self.assertIsNotNone(test_event.pk)
        #Assert that it is represented correctly
        self.assertEqual(str(test_event), 'Test Title')

    def test_datetime_validation(self):
        #Set Up
        test_event = Event(
            title="Test Title",
            description="Testing Purposes Only",
            location="Test location",
            start_time=now + timedelta(days=1),
            end_time=now,
            capacity=100,
        )
        #Test
        #Assert that selecting an end_time that is earlier than start_time throws a ValidationError
        with self.assertRaises(ValidationError) as cm:
            test_event.save()
        self.assertIn("end_time", cm.exception.message_dict)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_DIR, ignore_errors=True)
    def test_banner_image_upload(self):
        #Set Up : Creating a mock gif to simulate the upload of image on the webpage
        test_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
            b"\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00"
            b"\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
        )
        image = SimpleUploadedFile(
            name='test.gif', content=test_gif, content_type='image/gif'
        )
        event = Event.objects.create(
            title="Image Test",
            location="Venue",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=2),
            capacity=50,
            banner_image=image,
        )
        #Test
        self.assertTrue(event.banner_image.name.startswith('events/banners/')) 

#'Ticket' Tests
class TicketModelTest(TestCase):
    def setUp(self):
        self.test_event = Event.objects.create(
            title = 'Test Title',
            description = 'Testing Purposes Only',
            location = 'Test location',
            start_time = now + timedelta(days=1),
            end_time = now + timedelta(days=1, hours=3),
            capacity = 100
        )

    def test_correct_str_representation(self):
        #Set Up
        test_ticket = Ticket.objects.create(
            event = self.test_event,
            tier_name = 'VIP',
            price = 9.99,
            quantity_available = 65
        )
        #Test
        self.assertIsNotNone(test_ticket.pk)
        self.assertEqual(str(test_ticket), 'Test Title - VIP')

    def test_unique_tier_constraint(self):
        #Set Up
        test_ticket1 = Ticket.objects.create(
            event = self.test_event,
            tier_name = 'VIP',
            price = 9.99,
            quantity_available = 65
        )
        test_ticket2 = Ticket(
            event = self.test_event,
            tier_name = 'VIP',
            price = 12.99,
            quantity_available = 45
        )
        #Test
        with self.assertRaises(IntegrityError):
            test_ticket2.save()

    def test_negative_price_validation(self):
        #Set Up
        test_ticket = Ticket(
            event = self.test_event,
            tier_name = 'VIP',
            price = -9.99,
            quantity_available = 65
        )
        #Test
        with self.assertRaises(ValidationError):
            test_ticket.full_clean()

    def test_reverse_lookup(self):
        #Set Up
        test_ticket1 = Ticket.objects.create(
            event = self.test_event,
            tier_name = 'VIP',
            price = 9.99,
            quantity_available = 65
        )
        test_ticket2 = Ticket.objects.create(
            event = self.test_event,
            tier_name = 'Test',
            price = 19.99,
            quantity_available = 35
        )
        #Test
        tickets = self.test_event.tickets.all()
        self.assertEqual(tickets.count(), 2)
        self.assertIn(test_ticket1, tickets)
        self.assertIn(test_ticket2, tickets)

#'Booking' Tests
class BookingModelTest(TestCase):
    def setUp(self):
        self.test_user = User.objects.create(username='test_user', password='password123')

    def test_correct_str_representation_and_default(self):
        #Set Up
        test_booking = Booking.objects.create(
            user = self.test_user,
            total_price = 90.99
        )
        #Test
        self.assertEqual(str(test_booking), f'Booking #{test_booking.pk} - test_user (Pending)')

    def test_reverse_lookup(self):
        #Set Up
        test_booking1 = Booking.objects.create(
            user = self.test_user,
            total_price = 20.99
        )
        test_booking2 = Booking.objects.create(
            user = self.test_user,
            total_price = 80.99
        )
        bookings = self.test_user.bookings.all()
        #Test
        self.assertEqual(bookings.count(), 2)
        self.assertIn(test_booking1, bookings)
        self.assertIn(test_booking2, bookings)

#'BookingItem' Tests
class BookingItemModelTest(TestCase):
    def setUp(self):
        self.test_user2 = User.objects.create(
            username = 'Test User',
            password = 'password123'
        )
        self.test_event = Event.objects.create(
            title = 'Test Title',
            description = 'Testing Purposes Only',
            location = 'Test location',
            start_time = now + timedelta(days=1),
            end_time = now + timedelta(days=1, hours=3),
            capacity = 100
        )
        self.test_booking = Booking.objects.create(
            user = self.test_user2,
            total_price = 70.99
        )
        self.test_ticket = Ticket.objects.create(
            event = self.test_event,
            tier_name = 'VIP',
            price = 9.99,
            quantity_available = 65
        )

    def test_correct_str_representation(self):
        #Set Up
        test_booking_item = BookingItem.objects.create(
            booking = self.test_booking,
            ticket_type = self.test_ticket,
            quantity = 5,
            unit_price = 90.00
        )
        #Test
        self.assertEqual(str(test_booking_item), f'5x VIP (Booking #{self.test_booking.pk})')

    def test_quantity_validation(self):
        #Set Up
        test_booking_item = BookingItem(
            booking = self.test_booking,
            ticket_type = self.test_ticket,
            quantity = 0,
            unit_price = 90.00
        )
        #Test
        with self.assertRaises(ValidationError):
            test_booking_item.full_clean()

    def test_reverse_lookup(self):
        #Set Up
        test_booking_item1 = BookingItem.objects.create(
            booking = self.test_booking,
            ticket_type = self.test_ticket,
            quantity = 5,
            unit_price = 90.00
        )
        test_booking_item2 = BookingItem.objects.create(
            booking = self.test_booking,
            ticket_type = self.test_ticket,
            quantity = 5,
            unit_price = 90.00
        )
        booking_items = self.test_booking.items.all()
        #Test
        self.assertEqual(booking_items.count(), 2)
        self.assertIn(test_booking_item1, booking_items)
        self.assertIn(test_booking_item2, booking_items)
