# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Section templates for the safety file. Content is data, not code.

Wording here is deliberately plain and makes no legal claim. It names what a
section is for and leaves the facts to the user. Section lists are "commonly
requested by buyers", never "required by law": which sections a given site
must have is for the contractor's safety officer and the buyer's
specification to decide.
"""

# Review record. Stays None until a registered OHS practitioner (and a lawyer
# for the notice wording) has signed off. While None, the review notice is
# printed on every page of every output.
REVIEW = None

SUPPORTED_JURISDICTIONS = ("ZA",)

REVIEW_NOTICE = (
    "TEMPLATE - NOT YET REVIEWED. This file was laid out by software from the "
    "information you entered. It has not been checked by a registered "
    "occupational health and safety practitioner. Have your safety officer "
    "review and sign it before use. It does not show that you comply with any "
    "law or with the buyer's safety specification."
)

# Supporting documents a buyer commonly asks to see inside a safety file.
# `key` is what the profile's documents[].type must say. Nothing here says
# the document is legally required; the gap report lists it as "not provided".
EVIDENCE_TYPES = [
    {"key": "coida_letter", "label": "COIDA Letter of Good Standing", "expires": True},
    {"key": "company_registration", "label": "Company registration (CIPC)", "expires": False},
    {"key": "public_liability", "label": "Public liability insurance", "expires": True},
    {"key": "safety_officer_registration", "label": "Safety officer registration certificate", "expires": True},
    {"key": "notification_of_construction_work", "label": "Notification of construction work (if the buyer asks)", "expires": False},
]

# Binder sections, in order. `source` names the profile key the section is
# built from; `min_rows` is how many entries make the section "filled".
SECTIONS = [
    {
        "key": "contractor_details",
        "title": "Contractor and site details",
        "source": "company",
        "intro": "Who the contractor is, where the work happens and who the client is.",
    },
    {
        "key": "policy",
        "title": "Health and safety policy",
        "source": "policy",
        "intro": (
            "The contractor's own statement of how it manages health and safety. "
            "The commitments below are a starting point; edit them to match how "
            "your company really works, then have them signed by the most senior "
            "person in the company."
        ),
        "default_commitments": [
            "Identify hazards on every site before work starts and review them when the work changes.",
            "Put controls in place for the risks found and check that they are used.",
            "Give workers the information, training and protective equipment their tasks need.",
            "Report and investigate every incident and near miss, and act on what is learned.",
            "Consult workers on health and safety and let them stop unsafe work.",
            "Review this policy at least once a year.",
        ],
    },
    {
        "key": "appointments",
        "title": "Responsible people",
        "source": "people",
        "min_rows": 1,
        "intro": (
            "People named by the contractor as responsible for health and safety on "
            "this site. Which written appointments a site needs is for your safety "
            "officer to confirm; attach each signed appointment letter."
        ),
        "columns": [("name", "Name"), ("role", "Role"), ("phone", "Phone"), ("appointed_on", "Appointed on")],
    },
    {
        "key": "risk_assessment",
        "title": "Risk assessment",
        "source": "hazards",
        "min_rows": 1,
        "intro": (
            "Hazards entered by the contractor for this site, with the controls it "
            "will use. Software does not decide hazards or ratings; a competent "
            "person on site must."
        ),
        "columns": [
            ("activity", "Activity"),
            ("hazard", "Hazard"),
            ("risk", "Risk (H/M/L)"),
            ("controls", "Controls"),
            ("responsible", "Responsible"),
        ],
    },
    {
        "key": "safe_work_procedures",
        "title": "Safe work procedures",
        "source": "procedures",
        "min_rows": 1,
        "intro": "Step-by-step procedures for the tasks in the risk assessment.",
    },
    {
        "key": "training",
        "title": "Training records",
        "source": "training",
        "min_rows": 1,
        "intro": "Training completed by people working on this site. Attach each certificate.",
        "columns": [("person", "Person"), ("course", "Course"), ("issued", "Issued"), ("expires", "Expires")],
    },
    {
        "key": "medicals",
        "title": "Medical fitness records",
        "source": "medicals",
        "min_rows": 0,
        "intro": "Medical fitness certificates, where the work or the buyer calls for them.",
        "columns": [("person", "Person"), ("issued", "Issued"), ("expires", "Expires")],
    },
    {
        "key": "ppe_register",
        "title": "PPE issue register",
        "source": "registers.ppe",
        "min_rows": 0,
        "blank_rows": 15,
        "intro": "Record each item of protective equipment issued. Blank rows are for use on site.",
        "columns": [("date", "Date"), ("person", "Person"), ("item", "Item"), ("signature", "Signature")],
    },
    {
        "key": "equipment_register",
        "title": "Equipment inspection register",
        "source": "registers.equipment",
        "min_rows": 0,
        "blank_rows": 15,
        "intro": "Tools and equipment on site, with the last and next inspection date.",
        "columns": [
            ("item", "Item"),
            ("serial", "Serial"),
            ("last_inspected", "Last inspected"),
            ("next_inspection", "Next inspection"),
        ],
    },
    {
        "key": "visitor_register",
        "title": "Visitor register",
        "source": "registers.visitors",
        "min_rows": 0,
        "blank_rows": 20,
        "intro": "Everyone who visits the site. Blank rows are for use on site.",
        "columns": [("date", "Date"), ("name", "Name"), ("company", "Company"), ("time_in", "In"), ("time_out", "Out")],
    },
    {
        "key": "incident_report",
        "title": "Incident report form",
        "source": "incidents",
        "min_rows": 0,
        "intro": "Use one form per incident or near miss. Past incidents entered are listed first.",
        "form_fields": [
            "Date and time",
            "Place on site",
            "People involved",
            "What happened",
            "Injuries or damage",
            "Immediate action taken",
            "Cause found",
            "Action to stop it happening again",
            "Reported by (name and signature)",
        ],
        "columns": [("date", "Date"), ("description", "What happened"), ("action", "Action taken")],
    },
    {
        "key": "supporting_documents",
        "title": "Supporting documents",
        "source": "documents",
        "intro": (
            "Documents buyers commonly ask to see in a safety file. 'Not provided' "
            "means the document was not supplied to this tool; it does not mean it "
            "is required for your site."
        ),
    },
]
