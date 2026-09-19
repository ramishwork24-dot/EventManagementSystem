from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic.edit import FormMixin
from django.utils import timezone
from django.db import transaction
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View

from .models import Event, Ticket, Booking, BookingItem
from .forms import BookingForm, EventForm, TicketFormSet

# Create your views here.

#EventListView is rsponsible for showing upcoming events on the homepage
class EventListView(ListView):
    model = Event
    context_object_name = 'events'
    paginate_by = 6
    template_name = 'event/event_home.html'

    def get_queryset(self):
        #This method views upcoming events sorted by nearest start time, prefetching tickets for query optimization
        return (
            Event.objects.filter(start_time__gte=timezone.now()).prefetch_related('tickets').order_by('start_time')
        )

#EventDetailView shows details of an event on the event details page.
class EventDetailView(DetailView, FormMixin):
    model = Event
    context_object_name = 'event'
    template_name = 'event/event_detail.html'
    form_class = BookingForm

    def get_object(self, queryset=None):
        #Database Query Optimization Method
        if queryset is None:
            queryset = self.get_queryset()
        return super().get_object(queryset.prefetch_related('tickets'))
    
    def get_form_kwargs(self):
        #Passes the event instance to BookingForm to fetch correct entries like quantity
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.object
        return kwargs
    
    def get_context_data(self, **kwargs):
        #Injects both the Event instance and the unbound BookingForm into template context.
        context = super().get_context_data(**kwargs)
        context['form'] = self.get_form()
        return context

#EventCreateView will give logged in users the feature to register their event via filling a form.
class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'event/event_form.html'

    def get_context_data(self, **kwargs):
        #The ticket formset will be injected within this form to work seamlessly inline in the event form
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['ticket_formset'] = TicketFormSet(self.request.POST, self.request.FILES)
        else:
            context['ticket_formset'] = TicketFormSet()
        return context
    
    def form_valid(self, form):
        #Validates both EventForm and TicketFormSet within an atomic transaction block
        context = self.get_context_data()
        ticket_formset = context['ticket_formset']
        if ticket_formset.is_valid():
            with transaction.atomic():
                # Assign organizer so Event.save() passes model validation
                form.instance.organizer = self.request.user
                self.object = form.save()
                ticket_formset.instance = self.object
                ticket_formset.save()
            return redirect(self.get_success_url())
        else:
            return self.form_invalid(form)
        
    def get_success_url(self):
        return reverse_lazy('event_detail', kwargs={'pk':self.object.pk})

#EventUpdateView will let the event organizers edit the event details while preserving inventory logic.
class EventUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'event/event_form.html'

    def test_func(self):
        #Ensures that only the event creator can access the update form.
        event = self.get_object()
        return event.organizer == self.request.user
    
    def get_context_data(self, **kwargs):
        #The ticket formset will be injected within this form to work seamlessly inline in the event form
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['ticket_formset'] = TicketFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            context['ticket_formset'] = TicketFormSet(instance=self.object)
        return context
    
    def form_valid(self, form):
        #Validates both EventForm and TicketFormSet within an atomic transaction block
        context = self.get_context_data()
        ticket_formset = context['ticket_formset']
        if ticket_formset.is_valid():
            #Inventory Guardrails Check
            for ticket_form in ticket_formset.forms:
                if ticket_form.cleaned_data and not ticket_form.cleaned_data.get('DELETE'):
                    ticket_instance = ticket_form.instance
                    if ticket_instance.pk:
                        tickets_sold = ticket_instance.get_tickets_sold_count()
                        new_available = ticket_form.cleaned_data.get('quantity_available')
                        if new_available < 0:
                            ticket_form.add_error(
                                'quantity_available',
                                f"Cannot reduce inventory below 0. ({tickets_sold} already sold).",
                            )
                            return self.form_invalid(form)
                        
            with transaction.atomic():
                self.object = form.save()
                ticket_formset.save()
            return redirect(self.get_success_url())
        else:
            return self.form_invalid(form)
        
    def get_success_url(self):
        return reverse_lazy('event_detail', kwargs={'pk':self.object.pk})

#BookingCreateView is the ticket order processing engine
class BookingCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        form = BookingForm(request.POST, event=event)

        if not form.is_valid():
            #First-pass form validation
            return render(request, 'event/event_detail.html', {'event':event, 'form':form})
        selected_tickets = form.get_selected_tickets()

        try:
            with transaction.atomic():
                #Begin atomic transaction block
                ticket_ids = [ticket.id for ticket, _ in selected_tickets]
                #Lock target Ticket rows in DB using select_for_update()
                locked_tickets_qs = Ticket.objects.select_for_update().filter(id__in=ticket_ids)
                locked_tickets = {t.id: t for t in locked_tickets_qs}
                #Strict inventory check against fresh, locked DB records
                for ticket, qty_requested in selected_tickets:
                    db_ticket = locked_tickets[ticket.id]
                    if db_ticket.quantity_available < qty_requested:
                        raise ValueError(f"Sorry, only {db_ticket.quantity_available} tickets left for {db_ticket.tier_name}.")
                #Create parent Booking record
                booking = Booking.objects.create(
                    user = request.user,
                    event = event
                )

                #Create line items & update inventory
                total_booking_cost = 0
                for ticket, qty_requested in selected_tickets:
                    db_ticket = locked_tickets[ticket.id]
                    item_cost = db_ticket.price * qty_requested
                    total_booking_cost += item_cost
                    BookingItem.objects.create(
                        booking = booking,
                        ticket = db_ticket,
                        quantity = qty_requested,
                        price_at_purchase = db_ticket.price,
                    )
                    db_ticket.quantity_available -= qty_requested
                    db_ticket.save()

                #Save total calculated price to booking
                booking.total_price = total_booking_cost
                booking.save()

            messages.success(request, 'Your booking was successfully processed!')
            return redirect('booking_confirmation', pk=booking.pk)
        
        except ValueError as error_msg:
            messages.error(request, str(error_msg))
            return redirect('event_detail', pk=event.pk)
        
#BookingConfirmationView informs the user that their booking has been successfully processed
class BookingConfirmationView(LoginRequiredMixin, DetailView):
    model = Booking
    template_name = 'event/booking_confirmation.html'
    context_object_name = 'booking'

    def get_queryset(self):
        #outputs only the bookings owned by request.user
        return (
            super().get_queryset().filter(user=self.request.user)
            .select_related('event').prefetch_related('items__ticket')
        )

#UserBookingListView shows a list of all the bookings made by the user, newest first.
class UserBookingListView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = 'event/user_booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 10

    def get_queryset(self):
        return (
            Booking.objects.filter(user=self.request.user)
            .select_related('event').prefetch_related('items__ticket').order_by('-created_at')
        )

