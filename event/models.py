from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

# Create your models here.

#Event model that represents the gathering or occasion
class Event(models.Model):
    #Database Fields
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organized_events')
    title = models.CharField(max_length=255, db_index=True) #Name of the event
    description = models.TextField(blank=True) #short description, optional
    location = models.CharField(max_length=255) #Venue
    start_time = models.DateTimeField(db_index=True) 
    end_time = models.DateTimeField() #timing of the event
    capacity = models.PositiveIntegerField(help_text="Maximum venue capacity") #attendees limit
    banner_image = models.ImageField(upload_to='events/banners/%Y/%m/', blank=True, null=True) #Custom Event Banner, optional
    created_at = models.DateTimeField(auto_now_add=True) #Automatic timestamp at the time of creation
    updated_at = models.DateTimeField(auto_now=True) #Automatic timestamp at the time of updation

    #Database Behaviour
    class Meta:
        ordering = ["-start_time"]
        verbose_name = "Event"
        verbose_name_plural = "Events"

    def clean(self):
        super().clean()
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValidationError({'end_time': "End time must be after start time."})
            
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

#Ticket model that represents the token or invitation to the event. ManyToOne related to the Event Model
class Ticket(models.Model):
    #Database Fields
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets") #Foreign Key to 'Event'
    tier_name = models.CharField(max_length=100) #Ticket Type Name e.g. VIP, Economy etc.
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))]) #Price of the Ticket
    quantity_available = models.PositiveIntegerField() #available stock
    #Database behaviour
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields = ['event', 'tier_name'],
                name = 'unique_event_ticket_tier'
            )
        ]
        verbose_name = "Ticket Tier"
        verbose_name_plural = "Ticket Tiers"
    def __str__(self):
        return f"{self.event.title} - {self.tier_name}"
    
    def get_tickets_sold_count(self):
        result = self.booking_items.aggregate(total_sold=models.Sum("quantity"))
        return result["total_sold"] or 0

#Booking model represents a user's transaction/reservation order.
class Booking(models.Model):
    #Choice Box
    class Status(models.TextChoices):
        PENDING = 'PEN', 'Pending'
        CONFIRMED = 'CON', 'Confirmed'
        CANCELLED = 'CAN', 'Cancelled'
    #Database Fields
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings') #Foreign Key to default user model
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField(max_length=3, choices=Status.choices, default=Status.PENDING) #Choice box for status of booking
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal('0.00'))])
    created_at = models.DateTimeField(auto_now_add=True) #Automatic timestamp at the time of creation
    updated_at = models.DateTimeField(auto_now=True) #Automatic timestamp at the time of updation

    #Database Behaviour
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"

    def __str__(self):
        return f"Booking #{self.pk} - {self.user} ({self.get_status_display()})"

#BookingItem is an intermediary between 'Ticket' and 'Booking'
class BookingItem(models.Model):
    #Database Fields
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="items")
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="booking_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])

    #Database Behaviour
    class Meta:
        verbose_name = "Booking Item"
        verbose_name_plural = "Booking Items"

    def __str__(self):
        return f"{self.quantity}x {self.ticket.tier_name} (Booking #{self.booking_id})"



    
