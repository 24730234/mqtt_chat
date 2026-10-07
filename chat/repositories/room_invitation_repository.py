from ..models import RoomInvitation


class RoomInvitationRepository:
    def create(self, conversation, sender, recipient):
        return RoomInvitation.objects.create(
            conversation=conversation,
            sender=sender,
            user=recipient,
        )

    def get_for_update(self, invitation_id):
        return (
            RoomInvitation.objects.select_for_update()
            .filter(invitation_id=invitation_id)
            .first()
        )

    def has_pending(self, conversation, recipient):
        return RoomInvitation.objects.filter(
            conversation=conversation,
            user=recipient,
            status=RoomInvitation.InvitationStatus.PENDING,
        ).exists()

    def save_status(self, invitation, status):
        invitation.status = status
        invitation.save(update_fields=["status"])
        return invitation

    def list_for_user(self, user):
        pending = RoomInvitation.objects.filter(
            status=RoomInvitation.InvitationStatus.PENDING
        ).select_related("conversation", "sender", "user")
        return {
            "room_incoming": pending.filter(user=user).order_by("-send_time"),
            "room_sent": pending.filter(sender=user).order_by("-send_time"),
        }
