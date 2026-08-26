#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Seed the running showcase (`docker compose up --build -d` +
`uv run scripts/setup-full-database.py`) with a representative set of synthetic
patients/appointments/encounters/observations/invoices/payments, entirely
through the real HTTP API - never a direct DB write - so `GET
http://localhost:5173/` has something to actually look at instead of an
empty clinic.

Every name below is fictional (SPEC.md's synthetic-data rule, README.md
Sec 8): a mix of well-known computing pioneers, matching the same fixture
convention apps/api's own test suite already uses (see e.g.
apps/api/tests/patient_api.rs's "Ada Lovelace"/"Grace Hopper"), so nothing
here reads as a plausible real patient record.

Usage:

  uv run scripts/seed-demo-data.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone

PRACTITIONERS = [
    "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1",
    "b2b2b2b2-b2b2-b2b2-b2b2-b2b2b2b2b2b2",
]

PATIENTS = [
    {
        "legalName": "Ada Lovelace",
        "dateOfBirth": "1985-06-15",
        "email": "ada.lovelace@example.invalid",
        "phone": "+1-555-0101",
        "city": "London",
    },
    {
        "legalName": "Grace Hopper",
        "dateOfBirth": "1972-12-09",
        "email": "grace.hopper@example.invalid",
        "phone": "+1-555-0102",
        "city": "Arlington",
    },
    {
        "legalName": "Alan Turing",
        "dateOfBirth": "1990-06-23",
        "email": "alan.turing@example.invalid",
        "phone": "+1-555-0103",
        "city": "Manchester",
    },
    {
        "legalName": "Katherine Johnson",
        "dateOfBirth": "1968-08-26",
        "email": "katherine.johnson@example.invalid",
        "phone": "+1-555-0104",
        "city": "Hampton",
    },
    {
        "legalName": "Margaret Hamilton",
        "dateOfBirth": "1979-08-17",
        "email": "margaret.hamilton@example.invalid",
        "phone": "+1-555-0105",
        "city": "Boston",
    },
    {
        "legalName": "Dorothy Vaughan",
        "dateOfBirth": "1975-03-20",
        "email": "dorothy.vaughan@example.invalid",
        "phone": "+1-555-0106",
        "city": "Newport News",
    },
    {
        "legalName": "Mary Jackson",
        "dateOfBirth": "1982-04-09",
        "email": "mary.jackson@example.invalid",
        "phone": "+1-555-0107",
        "city": "Hampton",
    },
    {
        "legalName": "Joan Clarke",
        "dateOfBirth": "1988-06-24",
        "email": "joan.clarke@example.invalid",
        "phone": "+1-555-0108",
        "city": "London",
    },
    {
        "legalName": "Evelyn Boyd Granville",
        "dateOfBirth": "1977-05-01",
        "email": "evelyn.granville@example.invalid",
        "phone": "+1-555-0109",
        "city": "Washington",
    },
    {
        "legalName": "Annie Easley",
        "dateOfBirth": "1965-04-23",
        "email": "annie.easley@example.invalid",
        "phone": "+1-555-0110",
        "city": "Cleveland",
    },
]


def request(
    base_url: str, method: str, path: str, body: dict | None = None
) -> tuple[int, dict]:
    url = f"{base_url}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            payload = resp.read()
            return resp.status, (json.loads(payload) if payload else {})
    except urllib.error.HTTPError as err:
        payload = err.read()
        return err.code, (json.loads(payload) if payload else {})


def wait_until_ready(base_url: str, timeout_s: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            status, body = request(base_url, "GET", "/ready")
            if status == 200 and body.get("postgres") and body.get("clickhouse"):
                return
        except OSError:
            pass
        time.sleep(1)
    print(
        f"seed-demo-data.py: {base_url}/ready did not become ready within {timeout_s}s",
        file=sys.stderr,
    )
    sys.exit(1)


def seed_patient(base_url: str, spec: dict, index: int) -> str:
    patient_id = str(uuid.uuid4())
    body = {
        "patientId": patient_id,
        "legalName": spec["legalName"],
        "preferredName": None,
        "dateOfBirth": spec["dateOfBirth"],
        "contact": {"email": spec["email"], "phone": spec["phone"]},
        "address": {
            "street": f"{100 + index} Example Street",
            "city": spec["city"],
            "postalCode": "00000",
            "country": "Testland",
        },
        "preferredLanguage": "en",
        "alternatePhoneNumbers": None,
        "notes": None,
        "clinicalNotes": None,
    }
    status, resp = request(base_url, "POST", "/api/patients", body)
    if status != 201:
        raise RuntimeError(
            f"create patient {spec['legalName']!r} failed ({status}): {resp}"
        )
    print(f"  patient      {spec['legalName']:<20} {patient_id}")
    return patient_id


def seed_appointment(
    base_url: str,
    patient_id: str,
    practitioner_id: str,
    scheduled_date: date,
    status: str,
    start: str = "09:00:00",
    end: str = "09:30:00",
) -> str:
    appointment_id = str(uuid.uuid4())
    body = {
        "appointmentId": appointment_id,
        "patientId": patient_id,
        "practitionerId": practitioner_id,
        "scheduledDate": scheduled_date.isoformat(),
        "slot": {"start": start, "end": end},
        "bufferDuration": None,
        "status": status,
        "reason": "Routine check-up",
        "notes": None,
    }
    resp_status, resp = request(base_url, "POST", "/api/appointments", body)
    if resp_status != 201:
        raise RuntimeError(
            f"create appointment for {patient_id} failed ({resp_status}): {resp}"
        )
    return appointment_id


def seed_encounter_with_observations(
    base_url: str,
    patient_id: str,
    practitioner_id: str,
    appointment_id: str,
    started_at: datetime,
) -> str:
    encounter_id = str(uuid.uuid4())
    body = {
        "encounterId": encounter_id,
        "patientId": patient_id,
        "practitionerId": practitioner_id,
        "appointmentId": appointment_id,
        "status": "completed",
        "startedAt": started_at.isoformat().replace("+00:00", "Z"),
        "endedAt": (started_at + timedelta(minutes=20))
        .isoformat()
        .replace("+00:00", "Z"),
        "expectedDuration": None,
        "reasonCode": None,
        "diagnoses": None,
    }
    status, resp = request(base_url, "POST", "/api/encounters", body)
    if status != 201:
        raise RuntimeError(
            f"create encounter for {patient_id} failed ({status}): {resp}"
        )

    observation = {
        "observationId": str(uuid.uuid4()),
        "code": "temperature",
        "temperatureCelsius": 36.8,
        "bloodPressureSystolic": 118,
        "bloodPressureDiastolic": 76,
        "pulseBpm": 68,
        "isAbnormal": False,
        "deviceId": None,
        "metadata": {"unit": "celsius"},
        "recordedAt": (started_at + timedelta(minutes=5))
        .isoformat()
        .replace("+00:00", "Z"),
    }
    status, resp = request(
        base_url, "POST", f"/api/encounters/{encounter_id}/observations", observation
    )
    if status != 201:
        raise RuntimeError(
            f"create observation for encounter {encounter_id} failed ({status}): {resp}"
        )
    return encounter_id


def seed_invoice(
    base_url: str,
    patient_id: str,
    encounter_id: str | None,
    issued_at: datetime,
    with_payment: bool,
) -> str:
    invoice_id = str(uuid.uuid4())
    body = {
        "invoiceId": invoice_id,
        "patientId": patient_id,
        "encounterId": encounter_id,
        "lines": [
            {
                "description": "Consultation",
                "quantity": 1,
                "unitPrice": "100.00",
                "lineTotal": "100.00",
            }
        ],
        "subtotal": "100.00",
        "tax": "25.00",
        "total": "125.00",
        "currency": "SEK",
        "billingPeriod": issued_at.strftime("%Y-%m"),
        "status": "issued",
        "issuedAt": issued_at.isoformat().replace("+00:00", "Z"),
        "dueDate": (issued_at + timedelta(days=30)).date().isoformat(),
    }
    status, resp = request(base_url, "POST", "/api/invoices", body)
    if status != 201:
        raise RuntimeError(f"create invoice for {patient_id} failed ({status}): {resp}")

    if with_payment:
        payment = {
            "paymentId": str(uuid.uuid4()),
            "amount": "125.00",
            "method": "card",
            "receivedAt": (issued_at + timedelta(days=1))
            .isoformat()
            .replace("+00:00", "Z"),
        }
        status, resp = request(
            base_url, "POST", f"/api/invoices/{invoice_id}/payments", payment
        )
        if status != 201:
            raise RuntimeError(
                f"record payment for invoice {invoice_id} failed ({status}): {resp}"
            )
    return invoice_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8080",
        help="apps/api base URL (default: %(default)s)",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    print(f"seed-demo-data.py: waiting for {base_url}/ready ...")
    wait_until_ready(base_url)

    today = date.today()
    # Keep the browser and full-stack demos interesting on any day they are
    # started: five completed visits provide history, while two appointments
    # share today and three more fill the near-future schedule.
    future_offsets = [0, 0, 1, 2, 3]
    future_slots = [
        ("09:00:00", "09:30:00"),
        ("10:30:00", "11:00:00"),
        ("13:00:00", "13:30:00"),
        ("14:00:00", "14:30:00"),
        ("15:30:00", "16:00:00"),
    ]
    print(f"seed-demo-data.py: seeding {len(PATIENTS)} patients against {base_url}")
    for index, spec in enumerate(PATIENTS):
        practitioner_id = PRACTITIONERS[index % len(PRACTITIONERS)]
        patient_id = seed_patient(base_url, spec, index)

        is_past = index < 5
        appointment_status = (
            "completed"
            if is_past
            else ("requested" if index == len(PATIENTS) - 1 else "confirmed")
        )
        scheduled_date = (
            today - timedelta(days=5 - index)
            if is_past
            else today + timedelta(days=future_offsets[index - 5])
        )
        start, end = ("09:00:00", "09:30:00") if is_past else future_slots[index - 5]
        appointment_id = seed_appointment(
            base_url,
            patient_id,
            practitioner_id,
            scheduled_date,
            appointment_status,
            start,
            end,
        )

        if appointment_status == "completed":
            started_at = datetime.combine(
                scheduled_date, datetime.min.time(), tzinfo=timezone.utc
            ) + timedelta(hours=9)
            encounter_id = seed_encounter_with_observations(
                base_url, patient_id, practitioner_id, appointment_id, started_at
            )
            issued_at = started_at + timedelta(hours=1)
            # Every other completed encounter gets its invoice paid, so the
            # analytics/summary views show a mix of paid and outstanding.
            seed_invoice(
                base_url,
                patient_id,
                encounter_id,
                issued_at,
                with_payment=(index % 2 == 0),
            )

    print("seed-demo-data.py: done - open http://localhost:5173/ to look around")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
