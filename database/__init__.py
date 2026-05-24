from .db import init_db, get_connection
from .contacts_repo import (
    insert_contact, insert_contacts_bulk,
    get_pending_contacts, update_contact_status, update_contact_fields,
    delete_contact, list_contacts, count_contacts_by_status,
    mark_responded_by_phone, was_sent_recently
)
from .campaigns_repo import (
    create_campaign, update_campaign_status,
    get_campaign, list_campaigns,
    log_message, get_campaign_stats,
    get_antiban_settings, save_antiban_settings,
    get_today_count, get_current_hour_count, increment_today_count,
    get_ai_settings, save_ai_settings,
    get_or_create_conversation, update_conversation,
    list_conversations_ai, set_modo_humano
)
from .outbound_repo import (
    create_outbound_message,
    update_outbound_message,
    get_latest_outbound_by_phone,
    get_outbound_by_message_id,
)
