from event.forms import EventForm, TicketFormSet, BookingForm
from event.models import Event, Ticket
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
now = timezone.now()

#Tests for EventForm
class EventFormTest(TestCase):
    def test_valid_form_data(self):
        #Set Up
        form_data = {
            'title' : 'Test Form',
            'description' : 'Testing Purposes Only',
            'location' : 'Test Location',
            'start_time' : (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_time' : (now + timedelta(days=1, hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'capacity' : 100,
        }
        form = EventForm(data=form_data)
        #Tests
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['title'], 'Test Form')
        self.assertEqual(form.cleaned_data['capacity'], 100)

    def test_datetime_parse_correctly(self):
        #Set Up
        form_data = {
            'title' : 'Test Form',
            'description' : 'Testing Purposes Only',
            'location' : 'Test Location',
            'start_time' : '2026-11-05T12:40',
            'end_time' : '2026-11-05T14:00',
            'capacity' : 100,
        }   
        form = EventForm(data=form_data)
        #Tests
        self.assertTrue(form.is_valid())
        start_dt = form.cleaned_data['start_time']
        end_dt = form.cleaned_data['end_time']
        self.assertIsInstance(start_dt, datetime)
        self.assertIsInstance(end_dt, datetime)

    def test_datetime_correct_sequence_validation(self):
        #Set Up
        form_data = {
            'title' : 'Test Form',
            'description' : 'Testing Purposes Only',
            'location' : 'Test Location',
            'start_time' : (now + timedelta(days=1, hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_time' : (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'capacity' : 100,
        }
        form = EventForm(data=form_data)
        #Test: end_time is earlier than start_time so an error should occur
        self.assertFalse(form.is_valid())

    def test_missing_fields_detection(self):
        #Set Up
        form_data = {
            'title' : '',# missing required input 
            'description' : 'Testing Purposes Only',
            'location' : 'Test Location',
            'start_time' : '', #missing required input
            'end_time' : (now + timedelta(days=1, hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'capacity' : 100,
        }
        form = EventForm(data=form_data)
        #Test
        self.assertFalse(form.is_valid())
        errors_caught = form.errors.as_data()
        title_error = errors_caught.get('title')
        start_time_error = errors_caught.get('start_time')
        self.assertIsNotNone(title_error)
        self.assertIsNotNone(start_time_error)

#Tests for TicketFormSet
class TicketFormSetTest(TestCase):
    #Inline formsets require management form data explicitly defined
    def setUp(self):
        self.event = Event.objects.create(
            title = 'Test Event',
            description = 'Testing Purposes Only',
            location = 'Test Location',
            start_time = now + timedelta(days=1),
            end_time = now + timedelta(days=1, hours=2),
            capacity = 200,
        )

    def test_valid_creation(self):
        #Set Up: prepare the required input plus the form management data
        formset_data = {
            #Form management data
            'tickets-TOTAL_FORMS' : '1',
            'tickets-INITIAL_FORMS' : '0',
            'tickets-MIN_NUM_FORMS' : '1',
            'tickets-MAX_NUM_FORMS' : '1000',
            #Form 0 field inputs
            'tickets-0-tier_name' : 'VIP',
            'tickets-0-price' : '149.99',
            'tickets-0-quantity_available' : '20',
        }
        formset = TicketFormSet(data=formset_data, instance=self.event)
        #Tests
        self.assertTrue(formset.is_valid())
        saved_tickets = formset.save()
        self.assertEqual(len(saved_tickets), 1)
        self.assertEqual(saved_tickets[0].event, self.event)
        self.assertEqual(saved_tickets[0].tier_name, 'VIP')

    def test_validate_min_forms(self):
        #Set Up
        formset_data = {
            #Form management data
            'tickets-TOTAL_FORMS' : '1',
            'tickets-INITIAL_FORMS' : '0',
            'tickets-MIN_NUM_FORMS' : '1',
            'tickets-MAX_NUM_FORMS' : '1000',
            #Form 0 field inputs (simulating an empty form)
            'tickets-0-tier_name' : '',
            'tickets-0-price' : '',
            'tickets-0-quantity_available' : '',
        }
        formset = TicketFormSet(data=formset_data, instance=self.event)
        #Tests
        self.assertFalse(formset.is_valid()) 

    def test_invalid_input_detection(self):
        #Set Up
        formset_data = {
            #Form management data
            'tickets-TOTAL_FORMS' : '1',
            'tickets-INITIAL_FORMS' : '0',
            'tickets-MIN_NUM_FORMS' : '1',
            'tickets-MAX_NUM_FORMS' : '1000',
            #Form 0 field inputs
            'tickets-0-tier_name' : '', #empty required field
            'tickets-0-price' : '-149.99', #invalid negative price
            'tickets-0-quantity_available' : '20',
        }
        formset = TicketFormSet(data=formset_data, instance=self.event)
        #Tests
        self.assertFalse(formset.is_valid())
        errors_caught = formset.errors
        self.assertIsNotNone(errors_caught)

#Tests for BookingForm
class BookingFormTest(TestCase):
    def setUp(self):
        self.event = Event.objects.create(
            title = 'Test Event',
            description = 'Testing Purposes Only',
            location = 'Test Location',
            start_time = now + timedelta(days=1),
            end_time = now + timedelta(days=1, hours=2),
            capacity = 35,
        )
        self.ticket1 = Ticket.objects.create(
            event = self.event,
            tier_name = 'VIP',
            price = Decimal('100.00'),
            quantity_available = 10,
        )
        self.ticket2 = Ticket.objects.create(
            event = self.event,
            tier_name = 'regular',
            price = Decimal('70.00'),
            quantity_available = 30,
        )     

    def test_valid_booking_submission(self):
        #Set Up
        form_data = {
            f'ticket_{self.ticket1.id}' : '3',
            f'ticket_{self.ticket2.id}' : '1',
        }       
        form = BookingForm(data=form_data, event=self.event)
        #Test
        self.assertTrue(form.is_valid())
        selected_tickets = form.get_selected_tickets()
        self.assertEqual(len(selected_tickets), 2)
        self.assertIn((self.ticket1, 3), selected_tickets)
        self.assertIn((self.ticket2, 1), selected_tickets)

    def test_zero_selection_prevention(self):
        #Set Up: simulating no selection of tickets
        form_data = {
            f'ticket_{self.ticket1.id}' : '0',
        }       
        form = BookingForm(data=form_data, event=self.event)
        #Test
        self.assertFalse(form.is_valid())
        self.assertIn('You must select at least one ticket to proceed.', form.non_field_errors())

    def test_stock_limit_check(self):
        #Set Up
        field_name = f'ticket_{self.ticket1.id}'
        form_data = {
            field_name : '11',
        }       
        form = BookingForm(data=form_data, event=self.event)
        #Test
        self.assertFalse(form.is_valid())
        self.assertIn(field_name, form.errors)
        expected_error = f'Only {self.ticket1.quantity_available} tickets available for {self.ticket1.tier_name}.'
        self.assertIn(expected_error, form.errors[field_name])

    def test_capacity_limit_check(self):
        #Set Up
        field_name1 = f'ticket_{self.ticket1.id}'
        field_name2 = f'ticket_{self.ticket2.id}'
        form_data = {
            field_name1 : '9', #these numbers are in stock but exceed capacity of the event
            field_name2 : '29',
        } 
        form = BookingForm(data=form_data, event=self.event)   
        #Test
        self.assertFalse(form.is_valid())   

