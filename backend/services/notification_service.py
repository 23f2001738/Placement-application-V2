"""
Notification Service
Handles creation and management of notifications
"""
from datetime import datetime
from database import db
from models.notification import Notification
from services.realtime import emit_notification


def create_notification(user_id, title, message, notification_type='info', related_id=None):
    """
    Create a new notification for a user
    
    Args:
        user_id: ID of the user
        title: Notification title
        message: Notification message
        notification_type: Type of notification (interview, application, deadline, etc.)
        related_id: ID of related entity (optional)
    """
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            related_id=related_id,
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()
        
        # Emit real-time notification if needed
        emit_notification(user_id, message, notification_type)
        
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"Error creating notification: {str(e)}")
        return None


def mark_as_read(notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.query.get(notification_id)
        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.session.commit()
            return notification
        return None
    except Exception as e:
        db.session.rollback()
        print(f"Error marking notification as read: {str(e)}")
        return None


def get_unread_count(user_id):
    """Get count of unread notifications for a user"""
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def get_notifications(user_id, limit=20, offset=0):
    """Get notifications for a user"""
    return Notification.query.filter_by(user_id=user_id).order_by(
        Notification.created_at.desc()
    ).limit(limit).offset(offset).all()


def delete_notification(notification_id):
    """Delete a notification"""
    try:
        Notification.query.filter_by(id=notification_id).delete()
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting notification: {str(e)}")
        return False


def clear_old_notifications(user_id, days=30):
    """Clear notifications older than specified days"""
    from datetime import timedelta
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted = Notification.query.filter(
            Notification.user_id == user_id,
            Notification.created_at < cutoff_date,
            Notification.is_read == True
        ).delete()
        db.session.commit()
        return deleted
    except Exception as e:
        db.session.rollback()
        print(f"Error clearing old notifications: {str(e)}")
        return 0


def bulk_create_notifications(user_ids, title, message, notification_type='info'):
    """Create notifications for multiple users"""
    try:
        notifications = []
        for user_id in user_ids:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                is_read=False
            )
            notifications.append(notification)
            emit_notification(user_id, message, notification_type)
        
        db.session.add_all(notifications)
        db.session.commit()
        return notifications
    except Exception as e:
        db.session.rollback()
        print(f"Error creating bulk notifications: {str(e)}")
        return []
