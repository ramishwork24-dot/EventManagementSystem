from django.contrib import admin
from django.utils.html import format_html
from .models import Event, Ticket, Booking, BookingItem

# Register your models here.

class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 1
    fields = ('tier_name', 'price', 'quantity_available')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'description', 'location', 'start_time', 'end_time', 'capacity', 'banner_preview')
    list_filter = ('start_time', 'created_at')
    search_fields = ('title', 'location', 'organizer__username', 'organizer__email')
    date_hierarchy = 'start_time'
    raw_id_fields = ('organizer',)
    inlines = [TicketInline]
    list_select_related = ('organizer',)

    def banner_preview(self, obj):
        if obj.banner_image:
            return format_html('<img src="{}" style="max-height: 40px; border-radius: 4px;" />', obj.banner_image.url())
        return '-'
    banner_preview.short_description = 'Banner'

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('tier_name', 'event', 'price', 'quantity_available')
    list_filter = ('event',)
    search_fields = ('tier_name', 'event__title')
    list_select_related = ('event',)

class BookingItemInline(admin.TabularInline):
    model = BookingItem
    extra = 0
    readonly_fields = ('ticket', 'quantity', 'price_at_purchase')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'event', 'total_price', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('id', 'user__username', 'user__email', 'event__title')
    date_hierarchy = 'created_at'
    readonly_fields = ('user', 'event', 'total_price', 'created_at')
    raw_id_fields = ('user', 'event')
    inlines = [BookingItemInline]
    list_select_related = ('user', 'event',)

    def has_add_permission(self, request):
        return False