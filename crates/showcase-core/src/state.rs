//! Concrete application state for the browser-hosted clinic runtime.
//!
//! This state is the application port for the in-memory runtime: core use
//! cases operate directly on generated records instead of going through
//! repository traits that only imitate SQL. The native API intentionally
//! keeps database transactions, query planning, and best-effort ClickHouse
//! writes in its adapters, while calling the same deterministic validation
//! and mapping functions as this crate.

use std::collections::HashMap;

use billing_core::billing::billing_invoice_db_v2::BillingInvoiceDbV2;
use billing_core::billing::billing_payment_received_v1::BillingPaymentReceivedV1;
use billing_core::billing::invoice_id::InvoiceId;
use clinic_core::patient::patient_id::PatientId;
use clinic_core::patient::patient_patient_db_v2::PatientPatientDbV2;
use clinic_core::scheduling::appointment_id::AppointmentId;
use clinic_core::scheduling::scheduling_appointment_db_v1::SchedulingAppointmentDbV1;
use clinical_core::clinical::clinical_encounter_db_v1::ClinicalEncounterDbV1;
use clinical_core::clinical::clinical_observation_v1::ClinicalObservationV1;
use clinical_core::clinical::encounter_id::EncounterId;

/// All mutable clinic records owned by one in-memory runtime.
///
/// Generated database/domain representations remain the source of truth. The
/// maps match identity lookups used throughout the product; observations and
/// payments stay as vectors because their current queries group them by their
/// parent encounter or invoice and showcase datasets are deliberately small.
#[derive(Debug, Clone, Default, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct ClinicState {
    pub(crate) patients: HashMap<PatientId, PatientPatientDbV2>,
    pub(crate) appointments: HashMap<AppointmentId, SchedulingAppointmentDbV1>,
    pub(crate) encounters: HashMap<EncounterId, ClinicalEncounterDbV1>,
    pub(crate) observations: Vec<ClinicalObservationV1>,
    pub(crate) invoices: HashMap<InvoiceId, BillingInvoiceDbV2>,
    pub(crate) payments: Vec<BillingPaymentReceivedV1>,
}

impl ClinicState {
    /// Returns whether this runtime contains no clinic records.
    pub fn is_empty(&self) -> bool {
        let counts = self.counts();
        counts.patients == 0
            && counts.appointments == 0
            && counts.encounters == 0
            && counts.observations == 0
            && counts.invoices == 0
            && counts.payments == 0
    }

    /// Returns collection sizes without exposing mutable storage internals.
    pub fn counts(&self) -> ClinicStateCounts {
        ClinicStateCounts {
            patients: self.patients.len(),
            appointments: self.appointments.len(),
            encounters: self.encounters.len(),
            observations: self.observations.len(),
            invoices: self.invoices.len(),
            payments: self.payments.len(),
        }
    }
}

/// Stable diagnostic view of the records held by [`ClinicState`].
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ClinicStateCounts {
    pub patients: usize,
    pub appointments: usize,
    pub encounters: usize,
    pub observations: usize,
    pub invoices: usize,
    pub payments: usize,
}

#[cfg(test)]
mod tests {
    use super::{ClinicState, ClinicStateCounts};

    #[test]
    fn new_state_has_no_records() {
        let state = ClinicState::default();

        assert!(state.is_empty());
        assert_eq!(state.counts(), ClinicStateCounts::default());
    }
}
