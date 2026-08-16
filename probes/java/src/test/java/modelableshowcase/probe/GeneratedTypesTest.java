// Java probe for Modelable-generated types (IMPLEMENTATION_PLAN.md Task 7.3):
// compile the linked generated artifacts and run construction/equality tests.
//
// Only the five value-type artifacts compiled by pom.xml are exercised here -
// they are the entire set of generated Java that compiles under the pinned 1.7.0
// release (UPSTREAM_FINDINGS.md #17/#18; see pom.xml's header comment). Each is
// a real generated Patient/Scheduling/Billing/Clinical domain value type, just
// without the named-type references those two emitter bugs break. Java records
// auto-generate equals/hashCode/toString from their components, so a probe needs
// no serializer dependency - construction + equality is the strongest check the
// task requires ("one serialization or equality/construction test").

package modelableshowcase.probe;

import billing.InvoiceLineV0;
import clinical.DiagnosisV0;
import patient.AddressV0;
import patient.ContactDetailsV0;
import scheduling.TimeRangeV0;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

class GeneratedTypesTest {

    @org.junit.jupiter.api.Test
    void patientAddress_constructsAndEquals() {
        var a = new AddressV0("1 Clinic Way", "Springfield", "12345", "US");
        var same = new AddressV0("1 Clinic Way", "Springfield", "12345", "US");
        var different = new AddressV0("2 Clinic Way", "Springfield", "12345", "US");

        assertEquals("1 Clinic Way", a.street());
        assertEquals("Springfield", a.city());
        assertEquals("12345", a.postalCode());
        assertEquals("US", a.country());
        assertEquals(a, same);
        assertEquals(a.hashCode(), same.hashCode());
        assertNotEquals(a, different);
    }

    @org.junit.jupiter.api.Test
    void patientContactDetails_optionalComponentsDefaultToEmpty() {
        var empty = new ContactDetailsV0(Optional.empty(), Optional.empty());
        var filled = new ContactDetailsV0(Optional.of("ada@example.test"), Optional.of("+1-555-0100"));

        assertEquals(Optional.empty(), empty.email());
        assertEquals(Optional.of("ada@example.test"), filled.email());
        assertEquals(Optional.of("+1-555-0100"), filled.phone());
        assertNotEquals(empty, filled);
    }

    @org.junit.jupiter.api.Test
    void schedulingTimeRange_holdsTimeOfDay() {
        var slot = new TimeRangeV0(LocalTime.of(9, 0), LocalTime.of(9, 30));

        assertEquals(LocalTime.of(9, 0), slot.start());
        assertEquals(LocalTime.of(9, 30), slot.end());
        assertEquals(new TimeRangeV0(LocalTime.of(9, 0), LocalTime.of(9, 30)), slot);
    }

    @org.junit.jupiter.api.Test
    void billingInvoiceLine_holdsMoney() {
        var line = new InvoiceLineV0(
            "Consultation",
            2L,
            new BigDecimal("75.50"),
            new BigDecimal("151.00")
        );

        assertEquals("Consultation", line.description());
        assertEquals(2L, line.quantity());
        assertEquals(new BigDecimal("75.50"), line.unitPrice());
        assertEquals(new BigDecimal("151.00"), line.lineTotal());
    }

    @org.junit.jupiter.api.Test
    void clinicalDiagnosis_holdsCodesAndDate() {
        var diagnosis = new DiagnosisV0(
            List.of("J06.9", "R05"),
            Optional.of("Acute upper respiratory infection"),
            LocalDate.of(2026, 8, 15),
            Optional.of(2L)
        );

        assertEquals(List.of("J06.9", "R05"), diagnosis.codes());
        assertEquals(Optional.of("Acute upper respiratory infection"), diagnosis.description());
        assertEquals(LocalDate.of(2026, 8, 15), diagnosis.diagnosedDate());
        assertEquals(Optional.of(2L), diagnosis.severityRank());
    }
}