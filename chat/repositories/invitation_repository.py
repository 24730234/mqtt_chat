from django.db.models import Q

from ..models import Invitation


class InvitationRepository:
    def create(self, sender, recipient):
        return Invitation.objects.create(sender=sender, user=recipient)

    def get(self, invitation_id):
        return Invitation.objects.filter(invitation_id=invitation_id).first()

    def has_pending_between(self, first, second):
        return Invitation.objects.filter(
            Q(sender=first, user=second) | Q(sender=second, user=first),
            status=Invitation.InvitationStatus.PENDING,
        ).exists()

    def save_status(self, invitation, status):
        invitation.status = status
        invitation.save(update_fields=["status"])
        return invitation
