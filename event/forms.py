from django import forms
from .models import Event, Ticket
from django.core.exceptions import ValidationError

#EventForm handles event creation and editing for organizers.
class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'location', 'start_time', 'end_time', 'capacity', 'banner_image']
        #custom widgets for better compatibility with the browser
        widgets = {
            'start_time' : forms.DateTimeInput(
                attrs={'type':'datetime-local', 'class':'form-control'},
                format="%Y-%m-%dT%H:%M"
            ),
            'end_time' : forms.DateTimeInput(
                attrs={'type':'datetime-local', 'class':'form-control'},
                format="%Y-%m-%dT%H:%M"
            ),
        }
    #To make sure that the datetime is parsed correctly
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_time'].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields['end_time'].input_formats = ["%Y-%m-%dT%H:%M"]

#TicketFormSet allows organizers to add, edit, or remove multiple ticket tiers directly on the event creation page.
TicketFormSet = forms.inlineformset_factory(
    Event, Ticket,
    fields=['tier_name', 'price', 'quantity_available'],
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)

#BookingForm is a user-facing ticket purchase form
class BookingForm(forms.Form):
    #custom __init__() to generate integer input fields dynamically for each available ticket tier.
    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event

        if event:
            # Dynamically create a quantity field for every ticket tier in this event
            for ticket in event.tickets.all():
                field_name = f'ticket_{ticket.id}'
                self.fields[field_name] = forms.IntegerField(
                    label=f'{ticket.tier_name} (${ticket.price})',
                    min_value=0,
                    initial=0,
                    required=False,
                    widget=forms.NumberInput(
                        attrs={
                            'class':'form-control',
                            'min':0,
                            'max':ticket.quantity_available,
                        }
                    ),
                )
    
    #custom clean for correct parsing
    def clean(self):
        cleaned_data = super().clean()
        if not self.event:
            raise ValidationError("An event context is required to process this booking.")

        total_tickets_requested = 0
        has_selection = False
        field_errors = {}

        # Iterate over self.fields instead of cleaned_data to stay immune to dictionary mutations
        for field_name in self.fields:
            if field_name.startswith('ticket_'):
                value = cleaned_data.get(field_name)
                if value and value > 0:
                    ticket_id = field_name.split('_')[1]
                    try:
                        ticket = self.event.tickets.get(id=ticket_id)
                    except Ticket.DoesNotExist:
                        raise ValidationError('Invalid ticket selection.')

                    if value > ticket.quantity_available:
                        field_errors[field_name] = (
                            f'Only {ticket.quantity_available} tickets available for {ticket.tier_name}.'
                        )

                    total_tickets_requested += value
                    has_selection = True

        # Attach field errors AFTER iteration completes
        for field_name, error_msg in field_errors.items():
            self.add_error(field_name, error_msg)

        if not has_selection:
            raise ValidationError('You must select at least one ticket to proceed.')

        if total_tickets_requested > self.event.capacity:
            raise ValidationError(
                f'Requested tickets ({total_tickets_requested}) exceed total remaining event capacity ({self.event.capacity}).'
            )

        return cleaned_data
    
    #Helper method to extract (ticket, quantity) tuples for view processing.
    def get_selected_tickets(self):
        selected = []
        for field_name, quantity in self.cleaned_data.items():
            if field_name.startswith('ticket_') and quantity and quantity > 0:
                ticket_id = field_name.split('_')[1]
                ticket = self.event.tickets.get(id=ticket_id)
                selected.append((ticket, quantity))
        return selected
    
