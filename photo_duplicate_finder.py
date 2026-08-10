import os
import sys
import json
import asyncio
import re
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from dotenv import load_dotenv
import getpass
from collections import defaultdict
from datetime import datetime

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

client = TelegramClient("session", api_id, api_hash)

# Safety settings
BATCH_SIZE = 50
DELAY_BETWEEN_BATCHES = 2
DELAY_BETWEEN_MESSAGES = 0.5
MAX_RETRIES = 3

# File to save channel names
CHANNELS_FILE = "saved_channels.json"
REPLACEMENTS_FILE = "replacements.json"

# Media type names
MEDIA_TYPES = {
    "photo": {"name": "Photos"},
    "video": {"name": "Videos"},
    "gif": {"name": "GIFs"},
    "document": {"name": "Documents"},
    "sticker": {"name": "Stickers"},
    "voice": {"name": "Voice Messages"},
    "audio": {"name": "Audio Files"},
}

def load_channels():
    """Load saved channels from file"""
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_channels(channels):
    """Save channels to file"""
    with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
        json.dump(channels, f, indent=2, ensure_ascii=False)

def load_replacements():
    """Load saved replacements from file"""
    if os.path.exists(REPLACEMENTS_FILE):
        try:
            with open(REPLACEMENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_replacements(replacements):
    """Save replacements to file"""
    with open(REPLACEMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(replacements, f, indent=2, ensure_ascii=False)

def get_channel_input():
    """Get channel name with saved channels support"""
    channels = load_channels()
    
    while True:
        if channels:
            print("\nSaved Channels:")
            print("-" * 40)
            for i, channel in enumerate(channels, 1):
                print(f"  [{i}] {channel}")
            print(f"  [0] Enter new channel")
            print(f"  [B] Back to Main Menu")
            print("-" * 40)
            
            choice = input("Select channel number (0 for new, B for back): ").strip()
            
            if choice.lower() == 'b':
                return None
            
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(channels):
                    return channels[idx-1]
                elif idx == 0:
                    break
                else:
                    print("Invalid selection!")
                    continue
        
        # New channel
        entity = input("Enter channel username (without @): ").strip()
        entity = entity.replace('@', '')
        
        if entity:
            # Ask to save
            save = input(f"Save '{entity}' for future? (y/n): ").lower().strip()
            if save in ['yes', 'y']:
                if entity not in channels:
                    channels.append(entity)
                    save_channels(channels)
                    print(f"Saved '{entity}' to channels list!")
            return entity
        
        print("No channel entered!")
        return None

def get_media_selection():
    """Let user select which media types to check"""
    print("\nSELECT MEDIA TYPES TO CHECK:")
    print("=" * 50)
    print("  [1] Photos")
    print("  [2] Videos")
    print("  [3] GIFs")
    print("  [4] Documents")
    print("  [5] Stickers")
    print("  [6] Voice Messages")
    print("  [7] Audio Files")
    print("  [8] ALL TYPES")
    print("  [9] PHOTOS + VIDEOS (Quick Select)")
    print("  [B] Back")
    print("=" * 50)
    
    selected = []
    
    while True:
        choice = input("Enter numbers separated by commas (e.g., 1,2,5) or 8 for all, B for back: ").strip()
        
        if choice.lower() == 'b':
            return None
        elif choice == '8':
            return list(MEDIA_TYPES.keys())
        elif choice == '9':
            return ['photo', 'video']
        
        try:
            numbers = [int(x.strip()) for x in choice.split(',')]
            media_keys = list(MEDIA_TYPES.keys())
            for num in numbers:
                if 1 <= num <= 7:
                    selected.append(media_keys[num-1])
            if selected:
                return selected
            else:
                print("Invalid selection! Please try again.")
        except:
            print("Invalid input! Please enter numbers separated by commas.")
    
    return selected

def get_media_type(msg):
    """Get the type of media in a message"""
    if msg.photo:
        return "photo"
    elif msg.video:
        return "video"
    elif msg.document:
        if msg.document.mime_type == "image/gif":
            return "gif"
        else:
            return "document"
    elif msg.sticker:
        return "sticker"
    elif msg.voice:
        return "voice"
    elif msg.audio:
        return "audio"
    return None

def get_media_name(msg):
    """Get name for media type"""
    media_type = get_media_type(msg)
    if media_type and media_type in MEDIA_TYPES:
        return MEDIA_TYPES[media_type]["name"]
    return "Unknown"

def get_media_id(msg):
    """Get unique ID for any media type"""
    if msg.photo:
        return f"photo_{msg.photo.id}"
    elif msg.video:
        return f"video_{msg.video.id}"
    elif msg.document:
        return f"document_{msg.document.id}"
    elif msg.sticker:
        return f"sticker_{msg.sticker.id}"
    elif msg.voice:
        return f"voice_{msg.voice.id}"
    elif msg.audio:
        return f"audio_{msg.audio.id}"
    return None

async def safe_delete_message(chat, msg_id, retry_count=0):
    """Safely delete a message with rate limit handling"""
    try:
        await client.delete_messages(chat, msg_id)
        return True
    except FloodWaitError as e:
        wait_time = e.seconds
        print(f"   Rate limited! Waiting {wait_time} seconds...")
        await asyncio.sleep(wait_time)
        if retry_count < MAX_RETRIES:
            return await safe_delete_message(chat, msg_id, retry_count + 1)
        else:
            print(f"   Failed to delete {msg_id} after {MAX_RETRIES} retries")
            return False
    except Exception as e:
        print(f"   Error deleting {msg_id}: {e}")
        return False

async def safe_edit_message(chat, msg_id, new_text, retry_count=0):
    """Safely edit a message with rate limit handling"""
    try:
        await client.edit_message(chat, msg_id, new_text)
        return True
    except FloodWaitError as e:
        wait_time = e.seconds
        print(f"   Rate limited! Waiting {wait_time} seconds...")
        await asyncio.sleep(wait_time)
        if retry_count < MAX_RETRIES:
            return await safe_edit_message(chat, msg_id, new_text, retry_count + 1)
        else:
            print(f"   Failed to edit {msg_id} after {MAX_RETRIES} retries")
            return False
    except Exception as e:
        print(f"   Error editing {msg_id}: {e}")
        return False

async def safe_iter_messages(chat, limit=None):
    """Safely iterate messages with rate limit handling"""
    messages = []
    try:
        if limit is None:
            print(f"\nFetching ALL messages from channel...")
            print("This may take a while for large channels...")
            async for msg in client.iter_messages(chat):
                messages.append(msg)
                if len(messages) % 50 == 0:
                    print(f"   Fetched {len(messages)} messages so far...")
                    await asyncio.sleep(0.1)
        else:
            print(f"\nFetching {limit} messages...")
            async for msg in client.iter_messages(chat, limit=limit):
                messages.append(msg)
                if len(messages) % 50 == 0:
                    await asyncio.sleep(0.1)
    except FloodWaitError as e:
        wait_time = e.seconds
        print(f"   Rate limited! Waiting {wait_time} seconds...")
        await asyncio.sleep(wait_time)
        return await safe_iter_messages(chat, limit)
    
    return messages

def create_replacement_list():
    """Create a list of replacements"""
    replacements = []
    
    print("\nCREATE REPLACEMENT LIST")
    print("=" * 50)
    
    if os.path.exists("replacements.txt"):
        load_file = input("Load replacements from replacements.txt? (y/n): ").lower().strip()
        if load_file in ['yes', 'y']:
            try:
                with open("replacements.txt", 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '→' in line:
                            parts = line.split('→')
                            if len(parts) == 2:
                                search = parts[0].strip()
                                replace = parts[1].strip()
                                if search and replace:
                                    replacements.append({'search': search, 'replace': replace})
                if replacements:
                    print(f"Loaded {len(replacements)} replacements from file!")
                    return replacements
            except Exception as e:
                print(f"Error loading file: {e}")
    
    print("\nEnter replacements one by one.")
    print("Format: search_text -> replace_text")
    print("Type 'done' when finished")
    print("-" * 50)
    
    while True:
        entry = input("Replace: ").strip()
        
        if entry.lower() == 'done':
            if replacements:
                save_name = input("\nSave this list for future use? (y/n): ").lower().strip()
                if save_name in ['yes', 'y']:
                    name = input("Enter a name for this list: ").strip()
                    if name:
                        saved = load_replacements()
                        saved.append({
                            'name': name,
                            'replacements': replacements,
                            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        save_replacements(saved)
                        print(f"Saved list '{name}' with {len(replacements)} replacements!")
                return replacements
            else:
                print("No replacements defined!")
                return None
        
        if '→' in entry:
            parts = entry.split('→')
            if len(parts) == 2:
                search = parts[0].strip()
                replace = parts[1].strip()
                if search and replace:
                    replacements.append({'search': search, 'replace': replace})
                    print(f"   Added: '{search}' -> '{replace}' ({len(replacements)} total)")
                else:
                    print("Invalid format! Use: search -> replace")
            else:
                print("Invalid format! Use: search -> replace")
        else:
            print("Invalid format! Use: search -> replace")
    
    return replacements

async def run_duplicate_finder():
    """Run duplicate finder - goes directly to channel selection"""
    print("\n" + "="*70)
    print("  DUPLICATE FINDER")
    print("="*70)
    
    # Get channel
    entity = get_channel_input()
    if entity is None:
        return
    
    try:
        chat = await client.get_entity(entity)
    except Exception as e:
        print(f"Could not find channel: {e}")
        input("\nPress Enter to continue...")
        return
    
    # Get scan range
    print("\nSCAN RANGE:")
    print("=" * 50)
    print("  [1] Scan ALL messages")
    print("  [2] Scan specific number of messages")
    print("  [B] Back")
    print("=" * 50)
    
    range_choice = input("Choose (1, 2, or B for back): ").strip()
    
    if range_choice.lower() == 'b':
        return
    
    limit = None
    if range_choice == '2':
        try:
            limit = int(input("Enter number of messages to scan: ").strip())
            print(f"Will scan last {limit} messages")
        except ValueError:
            print("Invalid number! Using ALL messages.")
            limit = None
    elif range_choice == '1':
        print("Will scan ALL messages")
    else:
        print("Invalid choice! Using ALL messages.")
    
    # Get media selection
    selected_media = get_media_selection()
    if selected_media is None:
        return
    
    print("\nSelected Media Types:")
    print("-" * 40)
    for media in selected_media:
        print(f"  {MEDIA_TYPES[media]['name']}")
    print("-" * 40)
    
    confirm = input("\nContinue with these selections? (y/n): ").lower().strip()
    if confirm not in ['yes', 'y']:
        print("Cancelled by user")
        return
    
    # Fetch messages
    messages = await safe_iter_messages(chat, limit)
    
    if not messages:
        print("No messages found!")
        input("\nPress Enter to continue...")
        return
    
    print(f"Fetched {len(messages)} total messages")
    print("-" * 50)
    
    # Find duplicates
    print("Analyzing messages for duplicates...")
    media_map = defaultdict(list)
    
    media_counts = {media: 0 for media in selected_media}
    
    for msg in messages:
        media_type = get_media_type(msg)
        if media_type and media_type in selected_media:
            media_counts[media_type] = media_counts.get(media_type, 0) + 1
            media_id = get_media_id(msg)
            if media_id:
                media_map[media_id].append(msg)
    
    # Show counts
    print("\nMedia found:")
    for media, count in media_counts.items():
        if count > 0:
            print(f"  {MEDIA_TYPES[media]['name']}: {count}")
    print("-" * 50)
    
    # Only keep groups with more than 1 message
    duplicates = {mid: msgs for mid, msgs in media_map.items() if len(msgs) > 1}
    
    if not duplicates:
        print("No exact duplicate media found!")
        input("\nPress Enter to continue...")
        return
    
    # Display results
    print(f"\nFound {len(duplicates)} EXACT duplicate groups:\n")
    print("=" * 70)
    
    total_duplicates = 0
    for group_idx, (media_id, msgs) in enumerate(duplicates.items(), 1):
        sorted_msgs = sorted(msgs, key=lambda x: x.date)
        duplicate_count = len(sorted_msgs) - 1
        total_duplicates += duplicate_count
        
        media_name = get_media_name(sorted_msgs[0])
        
        print(f"\nDUPLICATE GROUP #{group_idx}")
        print(f"   {media_name} (ID: {media_id})")
        print(f"   {len(msgs)} copies found ({duplicate_count} duplicates)")
        print("-" * 70)
        
        print(f"\nORIGINAL (OLDEST - WILL BE KEPT):")
        print(f"   ID: {sorted_msgs[0].id}")
        print(f"   Date: {sorted_msgs[0].date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Link: https://t.me/{entity}/{sorted_msgs[0].id}")
        
        print(f"\nDUPLICATES (WILL BE DELETED):")
        for i, msg in enumerate(sorted_msgs[1:], 1):
            print(f"   {i}. ID: {msg.id} | Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"      Link: https://t.me/{entity}/{msg.id}")
        
        print("=" * 70)
    
    print(f"\nSummary: {len(duplicates)} groups, {total_duplicates} duplicates found")
    if limit is None:
        print(f"Total messages scanned: {len(messages)} (ALL messages)")
    else:
        print(f"Total messages scanned: {len(messages)} (last {limit})")
    
    # Ask for confirmation
    if total_duplicates > 0:
        delete_choice = input(f"\nDelete {total_duplicates} duplicate media? (y/n): ").lower().strip()
        
        if delete_choice in ['yes', 'y']:
            print("\nDeleting duplicates (keeping oldest)...")
            print(f"Safety: Deleting in batches of {BATCH_SIZE}")
            
            # Save report
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            with open(f"duplicates_{timestamp}.txt", "w", encoding="utf-8") as f:
                f.write(f"DUPLICATE MEDIA DELETED - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Channel: {entity}\n")
                f.write(f"Total messages scanned: {len(messages)}\n")
                f.write(f"Media types checked: {', '.join(selected_media)}\n")
                if limit:
                    f.write(f"Limit: {limit}\n")
                else:
                    f.write(f"Limit: ALL messages\n")
                f.write("="*70 + "\n\n")
                
                for group_idx, (media_id, msgs) in enumerate(duplicates.items(), 1):
                    sorted_msgs = sorted(msgs, key=lambda x: x.date)
                    media_name = get_media_name(sorted_msgs[0])
                    
                    f.write(f"DUPLICATE GROUP #{group_idx} ({media_name})\n")
                    f.write(f"Media ID: {media_id}\n")
                    f.write(f"Total copies: {len(msgs)}\n")
                    f.write("-"*50 + "\n")
                    
                    f.write(f"\nORIGINAL (KEPT):\n")
                    f.write(f"   Message ID: {sorted_msgs[0].id}\n")
                    f.write(f"   Date: {sorted_msgs[0].date.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"   Link: https://t.me/{entity}/{sorted_msgs[0].id}\n")
                    
                    f.write(f"\nDELETED DUPLICATES:\n")
                    for i, msg in enumerate(sorted_msgs[1:], 1):
                        f.write(f"   #{i} Message ID: {msg.id}\n")
                        f.write(f"      Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"      Link: https://t.me/{entity}/{msg.id}\n")
                        f.write(f"      ---\n")
                    f.write("\n" + "="*70 + "\n\n")
            
            # Delete duplicates in batches
            deleted_count = 0
            failed_count = 0
            batch_num = 0
            
            all_to_delete = []
            for media_id, msgs in duplicates.items():
                sorted_msgs = sorted(msgs, key=lambda x: x.date)
                all_to_delete.extend(sorted_msgs[1:])
            
            for i in range(0, len(all_to_delete), BATCH_SIZE):
                batch = all_to_delete[i:i+BATCH_SIZE]
                batch_num += 1
                
                print(f"\n   Batch {batch_num}: Deleting {len(batch)} messages...")
                
                for msg in batch:
                    success = await safe_delete_message(chat, msg.id)
                    if success:
                        deleted_count += 1
                        print(f"      Deleted message {msg.id}")
                    else:
                        failed_count += 1
                        print(f"      Failed to delete {msg.id}")
                    
                    await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
                
                if i + BATCH_SIZE < len(all_to_delete):
                    print(f"   Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
                    await asyncio.sleep(DELAY_BETWEEN_BATCHES)
            
            print(f"\nDeleted {deleted_count} duplicate media!")
            if failed_count > 0:
                print(f"Failed to delete {failed_count} messages")
            print("Kept the original/oldest copy for each group.")
            print(f"Report saved to: duplicates_{timestamp}.txt")
        else:
            print("No deletions performed.")
    else:
        print("No duplicates to delete!")
    
    input("\nPress Enter to continue...")

async def run_auto_editor():
    """Run auto-editor - goes directly to channel selection"""
    print("\n" + "="*70)
    print("  AUTO-EDITOR (Single Replacement)")
    print("="*70)
    
    # Get channel
    entity = get_channel_input()
    if entity is None:
        return
    
    try:
        chat = await client.get_entity(entity)
    except Exception as e:
        print(f"Could not find channel: {e}")
        input("\nPress Enter to continue...")
        return
    
    print("\n" + "="*70)
    print("  AUTO-EDITOR (Single Replacement)")
    print("="*70)
    print("\nThis will EDIT messages containing specific text.")
    print("Works with: Text messages AND Media captions!")
    print()
    
    # Get text to search for
    search_text = input("Enter the text to search for (case insensitive): ").strip()
    if not search_text:
        print("No text entered!")
        input("\nPress Enter to continue...")
        return
    
    # Get replacement text
    replace_text = input("Enter the text to replace it with: ").strip()
    if not replace_text:
        print("No replacement text entered!")
        input("\nPress Enter to continue...")
        return
    
    # Ask what to edit
    print("\nWhat would you like to edit?")
    print("  [1] Text messages only")
    print("  [2] Media captions only")
    print("  [3] Both (text messages AND captions)")
    edit_choice = input("Choose (1, 2, or 3): ").strip()
    
    # Get confirmation
    print(f"\nWill search for: '{search_text}'")
    print(f"Will replace with: '{replace_text}'")
    
    if edit_choice == '1':
        print("Target: Text messages only")
    elif edit_choice == '2':
        print("Target: Media captions only")
    else:
        print("Target: Both text messages and captions")
    
    print("All matching content will be EDITED!")
    
    confirm = input("\nContinue? (yes/no): ").lower().strip()
    if confirm not in ['yes', 'y']:
        print("Cancelled")
        input("\nPress Enter to continue...")
        return
    
    # Fetch messages
    limit = None
    limit_input = input("\nHow many messages to search? (Enter for ALL, or enter number): ").strip()
    if limit_input.isdigit():
        limit = int(limit_input)
    
    messages = await safe_iter_messages(chat, limit)
    
    if not messages:
        print("No messages found!")
        input("\nPress Enter to continue...")
        return
    
    print(f"Fetched {len(messages)} total messages")
    print("-" * 50)
    
    # Find messages containing the text in text OR caption
    found_messages = []
    search_lower = search_text.lower()
    
    print(f"\nSearching for '{search_text}'...")
    for msg in messages:
        text_to_check = ""
        content_type = ""
        should_check = False
        
        # Check text content
        if edit_choice in ['1', '3'] and msg.text:
            text_to_check = msg.text
            content_type = "Text message"
            should_check = True
        
        # Check caption (media messages)
        if edit_choice in ['2', '3'] and msg.media and msg.text:
            text_to_check = msg.text
            content_type = "Media caption"
            should_check = True
        
        # Check if search text is in the content
        if should_check and text_to_check and search_lower in text_to_check.lower():
            found_messages.append({
                'message': msg,
                'content_type': content_type,
                'original_text': text_to_check
            })
    
    if not found_messages:
        print(f"\nNo messages found containing '{search_text}'!")
        input("\nPress Enter to continue...")
        return
    
    # Show results
    print(f"\nFound {len(found_messages)} messages containing '{search_text}':\n")
    print("=" * 70)
    
    for i, item in enumerate(found_messages[:20], 1):
        msg = item['message']
        content_type = item['content_type']
        
        print(f"\nMESSAGE #{i}")
        print(f"   {content_type}")
        print(f"   ID: {msg.id}")
        print(f"   Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Link: https://t.me/{entity}/{msg.id}")
        
        if msg.photo:
            print(f"   Has photo")
        elif msg.video:
            print(f"   Has video")
        elif msg.document:
            print(f"   Has document")
        
        # Show original text
        preview = item['original_text'][:300]
        if len(item['original_text']) > 300:
            preview += "..."
        print(f"   Current: {preview}")
        
        print("-" * 40)
    
    if len(found_messages) > 20:
        print(f"\n... and {len(found_messages) - 20} more messages")
    
    print(f"\nTotal: {len(found_messages)} messages found")
    
    # Ask to edit
    edit_choice_confirm = input(f"\nEdit ALL {len(found_messages)} messages containing '{search_text}'? (y/n): ").lower().strip()
    
    if edit_choice_confirm in ['yes', 'y']:
        print(f"\nEditing {len(found_messages)} messages...")
        print(f"Replacing '{search_text}' with '{replace_text}'")
        print(f"Safety: Editing in batches of {BATCH_SIZE}")
        
        # Save report
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        with open(f"auto_edit_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(f"AUTO-EDITOR EDIT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Channel: {entity}\n")
            f.write(f"Search text: '{search_text}'\n")
            f.write(f"Replace with: '{replace_text}'\n")
            f.write(f"Messages found: {len(found_messages)}\n")
            f.write("="*70 + "\n\n")
            
            for i, item in enumerate(found_messages, 1):
                msg = item['message']
                f.write(f"#{i} Message ID: {msg.id}\n")
                f.write(f"   Type: {item['content_type']}\n")
                f.write(f"   Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"   Link: https://t.me/{entity}/{msg.id}\n")
                f.write(f"   Original Text: {item['original_text'][:200]}\n")
                f.write(f"   ---\n")
        
        # Edit messages in batches
        edited_count = 0
        failed_count = 0
        batch_num = 0
        
        for i in range(0, len(found_messages), BATCH_SIZE):
            batch = found_messages[i:i+BATCH_SIZE]
            batch_num += 1
            
            print(f"\n   Batch {batch_num}: Editing {len(batch)} messages...")
            
            for item in batch:
                msg = item['message']
                original_text = item['original_text']
                
                # Replace text (case insensitive)
                new_text = re.sub(re.escape(search_text), replace_text, original_text, flags=re.IGNORECASE)
                
                # Edit the message
                success = await safe_edit_message(chat, msg.id, new_text)
                if success:
                    edited_count += 1
                    print(f"      Edited {item['content_type']} in message {msg.id}")
                else:
                    failed_count += 1
                    print(f"      Failed to edit message {msg.id}")
                
                await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
            
            if i + BATCH_SIZE < len(found_messages):
                print(f"   Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)
        
        print(f"\nEdited {edited_count} messages!")
        if failed_count > 0:
            print(f"Failed to edit {failed_count} messages")
        print(f"Report saved to: auto_edit_{timestamp}.txt")
    else:
        print("No edits performed.")
    
    input("\nPress Enter to continue...")

async def run_batch_auto_editor():
    """Run batch auto-editor - goes directly to channel selection"""
    print("\n" + "="*70)
    print("  BATCH AUTO-EDITOR (Multiple Replacements)")
    print("="*70)
    
    # Get channel
    entity = get_channel_input()
    if entity is None:
        return
    
    try:
        chat = await client.get_entity(entity)
    except Exception as e:
        print(f"Could not find channel: {e}")
        input("\nPress Enter to continue...")
        return
    
    print("\n" + "="*70)
    print("  BATCH AUTO-EDITOR MODE")
    print("="*70)
    print("\nThis will apply MULTIPLE text replacements in one go.")
    print("Works with: Text messages AND Media captions!")
    print()
    
    # Load saved replacements
    saved_replacements = load_replacements()
    
    # Show saved replacements if any
    if saved_replacements:
        print("\nSaved Replacement Lists:")
        print("-" * 40)
        for i, rep in enumerate(saved_replacements, 1):
            name = rep.get('name', f'List {i}')
            count = len(rep.get('replacements', []))
            print(f"  [{i}] {name} ({count} replacements)")
        print(f"  [N] Create new replacement list")
        print(f"  [B] Back")
        print("-" * 40)
        
        choice = input("Choose a saved list, N for new, or B for back: ").strip()
        
        if choice.lower() == 'b':
            return
        
        if choice.lower() == 'n':
            replacements = create_replacement_list()
            if not replacements:
                return
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(saved_replacements):
                replacements = saved_replacements[idx-1]['replacements']
                print(f"\nUsing saved list: {saved_replacements[idx-1]['name']}")
            else:
                print("Invalid selection!")
                return
        else:
            print("Invalid input!")
            return
    else:
        print("\nNo saved replacement lists found.")
        print("Create a new replacement list:")
        replacements = create_replacement_list()
        if not replacements:
            return
    
    if not replacements:
        print("No replacements defined!")
        return
    
    # Show summary of replacements
    print("\nREPLACEMENT SUMMARY:")
    print("=" * 50)
    for i, rep in enumerate(replacements, 1):
        print(f"  {i}. '{rep['search']}' -> '{rep['replace']}'")
    print("=" * 50)
    
    # Ask what to edit
    print("\nWhat would you like to edit?")
    print("  [1] Text messages only")
    print("  [2] Media captions only")
    print("  [3] Both (text messages AND captions)")
    edit_choice = input("Choose (1, 2, or 3): ").strip()
    
    confirm = input("\nApply ALL these replacements to matching messages? (yes/no): ").lower().strip()
    if confirm not in ['yes', 'y']:
        print("Cancelled")
        return
    
    # Fetch messages
    limit = None
    limit_input = input("\nHow many messages to search? (Enter for ALL, or enter number): ").strip()
    if limit_input.isdigit():
        limit = int(limit_input)
    
    messages = await safe_iter_messages(chat, limit)
    
    if not messages:
        print("No messages found!")
        input("\nPress Enter to continue...")
        return
    
    print(f"Fetched {len(messages)} total messages")
    print("-" * 50)
    
    # Find messages containing any of the search texts
    found_messages = []
    search_terms = [rep['search'] for rep in replacements]
    
    print(f"\nSearching for {len(search_terms)} terms...")
    for msg in messages:
        text_to_check = ""
        content_type = ""
        should_check = False
        
        # Check text content
        if edit_choice in ['1', '3'] and msg.text:
            text_to_check = msg.text
            content_type = "Text message"
            should_check = True
        
        # Check caption (media messages)
        if edit_choice in ['2', '3'] and msg.media and msg.text:
            text_to_check = msg.text
            content_type = "Media caption"
            should_check = True
        
        # Check if any search term is in the content
        if should_check and text_to_check:
            text_lower = text_to_check.lower()
            for term in search_terms:
                if term.lower() in text_lower:
                    found_messages.append({
                        'message': msg,
                        'content_type': content_type,
                        'original_text': text_to_check
                    })
                    break
    
    if not found_messages:
        print(f"\nNo messages found containing any of the search terms!")
        input("\nPress Enter to continue...")
        return
    
    # Show results
    print(f"\nFound {len(found_messages)} messages containing search terms:\n")
    print("=" * 70)
    
    for i, item in enumerate(found_messages[:20], 1):
        msg = item['message']
        content_type = item['content_type']
        
        print(f"\nMESSAGE #{i}")
        print(f"   {content_type}")
        print(f"   ID: {msg.id}")
        print(f"   Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Link: https://t.me/{entity}/{msg.id}")
        
        if msg.photo:
            print(f"   Has photo")
        elif msg.video:
            print(f"   Has video")
        elif msg.document:
            print(f"   Has document")
        
        # Show original text with highlights
        preview = item['original_text'][:300]
        if len(item['original_text']) > 300:
            preview += "..."
        print(f"   Current: {preview}")
        
        print("-" * 40)
    
    if len(found_messages) > 20:
        print(f"\n... and {len(found_messages) - 20} more messages")
    
    print(f"\nTotal: {len(found_messages)} messages found")
    
    # Ask to edit
    edit_choice_confirm = input(f"\nApply ALL replacements to {len(found_messages)} messages? (y/n): ").lower().strip()
    
    if edit_choice_confirm in ['yes', 'y']:
        print(f"\nEditing {len(found_messages)} messages...")
        print(f"Applying {len(replacements)} replacements to each message")
        print(f"Safety: Editing in batches of {BATCH_SIZE}")
        
        # Save report
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        with open(f"batch_edit_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(f"BATCH AUTO-EDITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Channel: {entity}\n")
            f.write(f"Replacements applied: {len(replacements)}\n")
            f.write("="*70 + "\n\n")
            
            for i, rep in enumerate(replacements, 1):
                f.write(f"  {i}. '{rep['search']}' -> '{rep['replace']}'\n")
            
            f.write("\n" + "="*70 + "\n\n")
            f.write(f"Messages edited: {len(found_messages)}\n")
            f.write("="*70 + "\n\n")
            
            for i, item in enumerate(found_messages, 1):
                msg = item['message']
                f.write(f"#{i} Message ID: {msg.id}\n")
                f.write(f"   Type: {item['content_type']}\n")
                f.write(f"   Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"   Link: https://t.me/{entity}/{msg.id}\n")
                f.write(f"   Original Text: {item['original_text'][:200]}\n")
                f.write(f"   ---\n")
        
        # Edit messages in batches
        edited_count = 0
        failed_count = 0
        batch_num = 0
        
        for i in range(0, len(found_messages), BATCH_SIZE):
            batch = found_messages[i:i+BATCH_SIZE]
            batch_num += 1
            
            print(f"\n   Batch {batch_num}: Editing {len(batch)} messages...")
            
            for item in batch:
                msg = item['message']
                original_text = item['original_text']
                new_text = original_text
                
                # Apply all replacements
                for rep in replacements:
                    new_text = re.sub(re.escape(rep['search']), rep['replace'], new_text, flags=re.IGNORECASE)
                
                # Only edit if text changed
                if new_text != original_text:
                    success = await safe_edit_message(chat, msg.id, new_text)
                    if success:
                        edited_count += 1
                        print(f"      Edited {item['content_type']} in message {msg.id}")
                    else:
                        failed_count += 1
                        print(f"      Failed to edit message {msg.id}")
                else:
                    print(f"      No changes needed for message {msg.id}")
                
                await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
            
            if i + BATCH_SIZE < len(found_messages):
                print(f"   Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)
        
        print(f"\nEdited {edited_count} messages!")
        if failed_count > 0:
            print(f"Failed to edit {failed_count} messages")
        print(f"Report saved to: batch_edit_{timestamp}.txt")
    else:
        print("No edits performed.")
    
    input("\nPress Enter to continue...")

async def run_hashtag_cleaner():
    """Run hashtag cleaner - goes directly to channel selection"""
    print("\n" + "="*70)
    print("  HASHTAG CLEANER")
    print("="*70)
    
    # Get channel
    entity = get_channel_input()
    if entity is None:
        return
    
    try:
        chat = await client.get_entity(entity)
    except Exception as e:
        print(f"Could not find channel: {e}")
        input("\nPress Enter to continue...")
        return
    
    print("\n" + "="*70)
    print("  HASHTAG CLEANER MODE")
    print("="*70)
    print("\nThis will remove underscores from ALL hashtags.")
    print("Example: #Mushoku_Tensei -> #MushokuTensei")
    print("Works with: Text messages AND Media captions!")
    print()
    
    # Ask what to edit
    print("\nWhat would you like to edit?")
    print("  [1] Text messages only")
    print("  [2] Media captions only")
    print("  [3] Both (text messages AND captions)")
    edit_choice = input("Choose (1, 2, or 3): ").strip()
    
    confirm = input("\nRemove underscores from ALL hashtags in matching messages? (yes/no): ").lower().strip()
    if confirm not in ['yes', 'y']:
        print("Cancelled")
        return
    
    # Fetch messages
    limit = None
    limit_input = input("\nHow many messages to search? (Enter for ALL, or enter number): ").strip()
    if limit_input.isdigit():
        limit = int(limit_input)
    
    messages = await safe_iter_messages(chat, limit)
    
    if not messages:
        print("No messages found!")
        input("\nPress Enter to continue...")
        return
    
    print(f"Fetched {len(messages)} total messages")
    print("-" * 50)
    
    # Find messages with hashtags containing underscores
    found_messages = []
    hashtag_pattern = r'#([a-zA-Z0-9_]+)'
    
    print(f"\nSearching for hashtags with underscores...")
    for msg in messages:
        text_to_check = ""
        content_type = ""
        should_check = False
        
        # Check text content
        if edit_choice in ['1', '3'] and msg.text:
            text_to_check = msg.text
            content_type = "Text message"
            should_check = True
        
        # Check caption (media messages)
        if edit_choice in ['2', '3'] and msg.media and msg.text:
            text_to_check = msg.text
            content_type = "Media caption"
            should_check = True
        
        # Check if any hashtag with underscore exists
        if should_check and text_to_check:
            hashtags = re.findall(hashtag_pattern, text_to_check)
            if hashtags:
                for tag in hashtags:
                    if '_' in tag:
                        found_messages.append({
                            'message': msg,
                            'content_type': content_type,
                            'original_text': text_to_check,
                            'hashtags': hashtags
                        })
                        break
    
    if not found_messages:
        print(f"\nNo hashtags with underscores found!")
        input("\nPress Enter to continue...")
        return
    
    # Show results
    print(f"\nFound {len(found_messages)} messages with hashtags containing underscores:\n")
    print("=" * 70)
    
    for i, item in enumerate(found_messages[:20], 1):
        msg = item['message']
        content_type = item['content_type']
        
        print(f"\nMESSAGE #{i}")
        print(f"   {content_type}")
        print(f"   ID: {msg.id}")
        print(f"   Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Link: https://t.me/{entity}/{msg.id}")
        
        if msg.photo:
            print(f"   Has photo")
        elif msg.video:
            print(f"   Has video")
        
        # Show hashtags found
        hashtags_with_underscore = [h for h in item['hashtags'] if '_' in h]
        fixed_hashtags = [h.replace('_', '') for h in hashtags_with_underscore]
        
        print(f"\n   Hashtags found:")
        for j, tag in enumerate(hashtags_with_underscore, 1):
            print(f"      {j}. #{tag} -> #{fixed_hashtags[j-1]}")
        
        # Show preview
        preview = item['original_text'][:300]
        if len(item['original_text']) > 300:
            preview += "..."
        print(f"\n   Preview: {preview}")
        
        print("-" * 40)
    
    if len(found_messages) > 20:
        print(f"\n... and {len(found_messages) - 20} more messages")
    
    # Count total hashtags to fix
    total_hashtags = 0
    for item in found_messages:
        for tag in item['hashtags']:
            if '_' in tag:
                total_hashtags += 1
    
    print(f"\nTotal: {len(found_messages)} messages, {total_hashtags} hashtags to fix")
    
    # Ask to edit
    edit_choice_confirm = input(f"\nClean ALL hashtags in {len(found_messages)} messages? (y/n): ").lower().strip()
    
    if edit_choice_confirm in ['yes', 'y']:
        print(f"\nCleaning {len(found_messages)} messages...")
        print(f"Removing underscores from {total_hashtags} hashtags")
        print(f"Safety: Editing in batches of {BATCH_SIZE}")
        
        # Save report
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        with open(f"hashtag_clean_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(f"HASHTAG CLEANER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Channel: {entity}\n")
            f.write(f"Messages fixed: {len(found_messages)}\n")
            f.write(f"Hashtags fixed: {total_hashtags}\n")
            f.write("="*70 + "\n\n")
            
            for i, item in enumerate(found_messages, 1):
                msg = item['message']
                f.write(f"#{i} Message ID: {msg.id}\n")
                f.write(f"   Type: {item['content_type']}\n")
                f.write(f"   Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"   Link: https://t.me/{entity}/{msg.id}\n")
                hashtags_with_underscore = [h for h in item['hashtags'] if '_' in h]
                fixed_hashtags = [h.replace('_', '') for h in hashtags_with_underscore]
                for j, tag in enumerate(hashtags_with_underscore, 1):
                    f.write(f"   #{tag} -> #{fixed_hashtags[j-1]}\n")
                f.write(f"   ---\n")
        
        # Edit messages in batches
        edited_count = 0
        failed_count = 0
        batch_num = 0
        
        for i in range(0, len(found_messages), BATCH_SIZE):
            batch = found_messages[i:i+BATCH_SIZE]
            batch_num += 1
            
            print(f"\n   Batch {batch_num}: Editing {len(batch)} messages...")
            
            for item in batch:
                msg = item['message']
                original_text = item['original_text']
                new_text = original_text
                
                # Function to clean hashtags: remove underscores
                def clean_hashtag(match):
                    tag = match.group(1)
                    clean_tag = tag.replace('_', '')
                    return f'#{clean_tag}'
                
                # Apply hashtag cleaning
                new_text = re.sub(r'#([a-zA-Z0-9_]+)', clean_hashtag, new_text)
                
                # Only edit if text changed
                if new_text != original_text:
                    success = await safe_edit_message(chat, msg.id, new_text)
                    if success:
                        edited_count += 1
                        print(f"      Cleaned hashtags in {item['content_type']} message {msg.id}")
                    else:
                        failed_count += 1
                        print(f"      Failed to edit message {msg.id}")
                else:
                    print(f"      No changes needed for message {msg.id}")
                
                await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
            
            if i + BATCH_SIZE < len(found_messages):
                print(f"   Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)
        
        print(f"\nCleaned {edited_count} messages!")
        if failed_count > 0:
            print(f"Failed to edit {failed_count} messages")
        print(f"Report saved to: hashtag_clean_{timestamp}.txt")
    else:
        print("No edits performed.")
    
    input("\nPress Enter to continue...")

def manage_channels():
    """Manage saved channels"""
    print("\n" + "="*70)
    print("  MANAGE SAVED CHANNELS")
    print("="*70)
    
    channels = load_channels()
    if channels:
        print("\nCurrent saved channels:")
        print("-" * 40)
        for i, channel in enumerate(channels, 1):
            print(f"  [{i}] {channel}")
        print("-" * 40)
        
        clear = input("\nClear all saved channels? (y/n): ").lower().strip()
        if clear in ['yes', 'y']:
            save_channels([])
            print("All channels cleared!")
    else:
        print("\nNo saved channels found.")
        print("Run Duplicate Finder or Auto-Editor and save a channel first.")
    
    input("\nPress Enter to continue...")

def view_reports():
    """View reports"""
    while True:
        print("\n" + "="*70)
        print("  VIEW REPORTS")
        print("="*70)
        print("  [1] Duplicate Finder Reports")
        print("  [2] Auto-Editor Reports")
        print("  [3] Batch Auto-Editor Reports")
        print("  [4] Hashtag Cleaner Reports")
        print("  [B] Back")
        print("="*70)
        
        choice = input("\nChoose (1, 2, 3, 4, or B for back): ").strip()
        
        if choice.lower() == 'b':
            return
        
        if choice == '1':
            file_pattern = "duplicates_"
            title = "DUPLICATE FINDER REPORTS"
        elif choice == '2':
            file_pattern = "auto_edit_"
            title = "AUTO-EDITOR REPORTS"
        elif choice == '3':
            file_pattern = "batch_edit_"
            title = "BATCH AUTO-EDITOR REPORTS"
        elif choice == '4':
            file_pattern = "hashtag_clean_"
            title = "HASHTAG CLEANER REPORTS"
        else:
            print("Invalid choice!")
            continue
        
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
        print()
        
        files = [f for f in os.listdir('.') if f.startswith(file_pattern) and f.endswith('.txt')]
        if files:
            files.sort(reverse=True)
            for i, f in enumerate(files[:10], 1):
                print(f"  [{i}] {f}")
            print()
            
            file_choice = input("Enter report number (or press Enter for latest): ").strip()
            if file_choice.isdigit():
                idx = int(file_choice)
                if 1 <= idx <= len(files):
                    file = files[idx-1]
                else:
                    print("Invalid selection!")
                    continue
            else:
                file = files[0]
                print(f"Showing latest: {file}")
            
            if os.path.exists(file):
                with open(file, 'r', encoding='utf-8') as f:
                    print("\n" + "="*70)
                    print(f.read())
            else:
                print("File not found!")
        else:
            print("No reports found!")
        
        input("\nPress Enter to continue...")

def install_requirements():
    """Install requirements"""
    print("\n" + "="*70)
    print("  INSTALL REQUIREMENTS")
    print("="*70)
    print("\nInstalling required packages...")
    os.system('pip install telethon python-dotenv')
    print("\nInstallation complete!")
    input("\nPress Enter to continue...")

def create_env_file():
    """Create .env file"""
    print("\n" + "="*70)
    print("  CREATE .env FILE")
    print("="*70)
    
    if os.path.exists('.env'):
        overwrite = input("\n.env file already exists. Overwrite? (y/n): ").lower().strip()
        if overwrite not in ['yes', 'y']:
            print("Cancelled")
            input("\nPress Enter to continue...")
            return
    
    print("\nCreating .env file...")
    with open('.env', 'w') as f:
        f.write("API_ID=your_api_id_here\n")
        f.write("API_HASH=your_api_hash_here\n")
    
    print(".env file created!")
    print("\nPlease edit .env file with your credentials:")
    print("  - Get from: https://my.telegram.org/apps")
    
    edit = input("\nOpen .env for editing? (y/n): ").lower().strip()
    if edit in ['yes', 'y']:
        if os.name == 'nt':
            os.system('notepad .env')
        else:
            os.system('nano .env')
    
    input("\nPress Enter to continue...")

async def main_menu():
    """Main menu with all options - Clean version"""
    while True:
        print("\n" + "="*70)
        print("  DUPLICATE FINDER AND AUTO-EDITOR")
        print("="*70)
        print("  [1] Duplicate Finder (Find n Delete Duplicate Posts)")
        print("  [2] Auto-Editor (Auto Edit Any Caption n Text)")
        print("  [3] Batch Auto-Editor (Auto Edit By Batch)")
        print("  [4] Hashtag Cleaner (Removes _ From Your Hashtags)")
        print("  [5] Manage Saved Channels")
        print("  [6] View Reports")
        print("  [7] Install Requirements")
        print("  [8] Create .env File")
        print("  [9] Exit")
        print("="*70)
        
        choice = input("\nEnter your choice (1-9): ").strip()
        
        if choice == '1':
            await run_duplicate_finder()
        elif choice == '2':
            await run_auto_editor()
        elif choice == '3':
            await run_batch_auto_editor()
        elif choice == '4':
            await run_hashtag_cleaner()
        elif choice == '5':
            manage_channels()
        elif choice == '6':
            view_reports()
        elif choice == '7':
            install_requirements()
        elif choice == '8':
            create_env_file()
        elif choice == '9':
            print("\nGoodbye!")
            sys.exit(0)
        else:
            print("Invalid choice! Please try again.")

async def main():
    try:
        await client.start()
        me = await client.get_me()
        print(f"Logged in as: {me.first_name}")
        await main_menu()
    except SessionPasswordNeededError:
        password = getpass.getpass("Enter your 2FA password: ")
        await client.sign_in(password=password)
        await main_menu()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
