# Fungsi file: Penanganan request HTTP, scope akses, dan respons untuk proposal kerja sama dan approval Organizer.

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from .forms import ConfirmationForm
from .models import OrganizerProposal
from .services import create_proposal, delete_draft, edit_proposal, submit_proposal


def proposal_data(proposal):
    return {
        "id": proposal.pk, "organization_name": proposal.organization_name,
        "contact_information": proposal.contact_information, "proposal_text": proposal.proposal_text,
        "status": proposal.status, "submitted_at": proposal.submitted_at,
        "created_at": proposal.created_at, "updated_at": proposal.updated_at,
    }


# Inheritance: ApplicantView mewarisi dispatch request berdasarkan metode HTTP.
@method_decorator(never_cache, name="dispatch")
class ApplicantView(View):
    http_method_names = ["get", "post", "head", "options"]

    # Polymorphism: menambahkan pemeriksaan akses sebelum meneruskan request ke handler.
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        try:
            return super().dispatch(request, *args, **kwargs)
        except ValidationError as exc:
            errors = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
            return JsonResponse({"errors": errors}, status=400)


# Inheritance: ProposalListView mewarisi perilaku ApplicantView untuk diperluas sesuai kebutuhan class ini.
class ProposalListView(ApplicantView):
    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request):
        page = Paginator(OrganizerProposal.objects.owned_by(request.user), 20).get_page(request.GET.get("page"))
        return JsonResponse({"results": [proposal_data(proposal) for proposal in page],
                             "page": page.number, "pages": page.paginator.num_pages})

    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request):
        proposal = create_proposal(actor=request.user, data=request.POST)
        return JsonResponse(proposal_data(proposal), status=201)


# Inheritance: ProposalDetailView mewarisi perilaku ApplicantView untuk diperluas sesuai kebutuhan class ini.
class ProposalDetailView(ApplicantView):
    # Polymorphism: dispatch memilih handler GET ini sesuai jenis request dan class view.
    def get(self, request, pk):
        proposal = get_object_or_404(OrganizerProposal.objects.owned_by(request.user), pk=pk)
        data = proposal_data(proposal)
        # Reviewer identity and account-administration notes remain internal.
        data["reviews"] = list(proposal.reviews.values("from_status", "to_status", "reason", "created_at"))
        return JsonResponse(data)

    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, pk):
        return JsonResponse(proposal_data(edit_proposal(actor=request.user, proposal_id=pk, data=request.POST)))


# Inheritance: ProposalSubmitView mewarisi perilaku ApplicantView untuk diperluas sesuai kebutuhan class ini.
class ProposalSubmitView(ApplicantView):
    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, pk):
        return JsonResponse(proposal_data(submit_proposal(actor=request.user, proposal_id=pk)))


# Inheritance: ProposalDeleteView mewarisi perilaku ApplicantView untuk diperluas sesuai kebutuhan class ini.
class ProposalDeleteView(ApplicantView):
    # Polymorphism: dispatch memilih handler POST ini sesuai jenis request dan class view.
    def post(self, request, pk):
        # Resolve ownership even when the confirmation is missing.
        get_object_or_404(OrganizerProposal.objects.owned_by(request.user), pk=pk)
        form = ConfirmationForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        delete_draft(actor=request.user, proposal_id=pk)
        return JsonResponse({"deleted": True})
