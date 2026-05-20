from core.utils import get_default_school
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Conversation, Message
from schools.models import SchoolUser
from django.http import JsonResponse

@login_required
def conversation_list(request):
    """List all conversations for the current user in the current school"""
    conversations = request.user.conversations.filter(school=get_default_school()).prefetch_related('participants', 'messages')
    
    # Add 'other_participant' and unread count to each conversation object for the template
    for conv in conversations:
        conv.other_participant = conv.participants.exclude(id=request.user.id).first()
        conv.has_unread = conv.messages.filter(is_read=False).exclude(sender=request.user).exists()
        
    return render(request, 'messaging/list.html', {
        'conversations': conversations
    })

@login_required
def chat_view(request, conversation_id):
    """View and send messages in a conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    
    if request.method == 'POST':
        body = request.POST.get('body')
        if body:
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                body=body
            )
            # Update conversation timestamp for sorting
            conversation.save() 
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'ok'})
            return redirect('messaging:chat', conversation_id=conversation.id)

    messages = conversation.messages.all()
    # Mark messages from others as read
    conversation.messages.exclude(sender=request.user).update(is_read=True)
    
    # Get the other participant for the UI header
    other_participant = conversation.participants.exclude(id=request.user.id).first()

    return render(request, 'messaging/chat.html', {
        'conversation': conversation,
        'chat_messages': messages,
        'other_participant': other_participant
    })

@login_required
def start_conversation(request, user_id):
    """Start or resume a conversation with a specific user"""
    other_user = get_object_or_404(User, id=user_id)
    
    # Check if a conversation already exists between these two in this school
    conversation = Conversation.objects.filter(
        school=get_default_school(),
        participants=request.user
    ).filter(
        participants=other_user
    ).first()
    
    if not conversation:
        conversation = Conversation.objects.create(school=get_default_school())
        conversation.participants.add(request.user, other_user)
    
    return redirect('messaging:chat', conversation_id=conversation.id)

@login_required
def get_messages_ajax(request, conversation_id):
    """Endpoint for polling new messages"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    last_id = request.GET.get('last_id')
    
    new_messages = conversation.messages.all()
    if last_id:
        new_messages = new_messages.filter(id__gt=last_id)
    
    data = []
    for msg in new_messages:
        data.append({
            'id': msg.id,
            'sender': msg.sender.get_full_name() or msg.sender.username,
            'sender_id': msg.sender.id,
            'body': msg.body,
            'created_at': msg.created_at.strftime('%H:%M'),
            'is_me': msg.sender == request.user
        })
    
    # Mark as read
    new_messages.exclude(sender=request.user).update(is_read=True)
    
    return JsonResponse({'messages': data})
