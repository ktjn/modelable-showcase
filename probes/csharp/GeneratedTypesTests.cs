// C# probe for Modelable-generated types (IMPLEMENTATION_PLAN.md Task 7.2):
// compile the linked generated artifacts, instantiate representative types,
// and serialize at least one with System.Text.Json.
//
// Only the five value-type artifacts linked by ModelableShowcase.Probe.csproj
// are exercised here - they are the entire set of generated C# that compiles
// under the pinned 1.7.0 release (UPSTREAM_FINDINGS.md #15/#16; see the csproj
// header comment). Each is a real generated Patient/Scheduling/Billing/Clinical
// domain value type, just without the named-type references those two emitter
// bugs break.

using System.Text.Json;

namespace ModelableShowcase.Probe;

public class GeneratedTypesTests
{
    [Fact]
    public void PatientAddress_instantiates_and_round_trips()
    {
        var address = new Modelable.Patient.PatientAddressV0
        {
            Street = "1 Clinic Way",
            City = "Springfield",
            PostalCode = "12345",
            Country = "US",
        };

        Assert.Equal("1 Clinic Way", address.Street);
        Assert.Equal("Springfield", address.City);
        Assert.Equal("12345", address.PostalCode);
        Assert.Equal("US", address.Country);
    }

    [Fact]
    public void PatientContactDetails_optional_fields_default_to_null()
    {
        var contact = new Modelable.Patient.PatientContactDetailsV0();

        Assert.Null(contact.Email);
        Assert.Null(contact.Phone);

        var filled = contact with { Email = "ada@example.test", Phone = "+1-555-0100" };
        Assert.Equal("ada@example.test", filled.Email);
        Assert.Equal("+1-555-0100", filled.Phone);
    }

    [Fact]
    public void SchedulingTimeRange_holds_time_of_day()
    {
        var slot = new Modelable.Scheduling.SchedulingTimeRangeV0
        {
            Start = new TimeOnly(9, 0),
            End = new TimeOnly(9, 30),
        };

        Assert.Equal(new TimeOnly(9, 0), slot.Start);
        Assert.Equal(new TimeOnly(9, 30), slot.End);
    }

    [Fact]
    public void BillingInvoiceLine_holds_money()
    {
        var line = new Modelable.Billing.BillingInvoiceLineV0
        {
            Description = "Consultation",
            Quantity = 2,
            UnitPrice = 75.50m,
            LineTotal = 151.00m,
        };

        Assert.Equal("Consultation", line.Description);
        Assert.Equal(2, line.Quantity);
        Assert.Equal(75.50m, line.UnitPrice);
        Assert.Equal(151.00m, line.LineTotal);
    }

    [Fact]
    public void ClinicalDiagnosis_holds_codes_and_date()
    {
        var diagnosis = new Modelable.Clinical.ClinicalDiagnosisV0
        {
            Codes = ["J06.9", "R05"],
            Description = "Acute upper respiratory infection",
            DiagnosedDate = new DateOnly(2026, 8, 15),
            SeverityRank = 2,
        };

        Assert.Equal(["J06.9", "R05"], diagnosis.Codes);
        Assert.Equal(new DateOnly(2026, 8, 15), diagnosis.DiagnosedDate);
        Assert.Equal(2, diagnosis.SeverityRank);
    }

    [Fact]
    public void PatientAddress_serializes_and_deserializes_with_system_text_json()
    {
        var address = new Modelable.Patient.PatientAddressV0
        {
            Street = "1 Clinic Way",
            City = "Springfield",
            PostalCode = "12345",
            Country = "US",
        };

        var json = JsonSerializer.Serialize(address);

        Assert.Contains("\"Street\":\"1 Clinic Way\"", json);
        Assert.Contains("\"City\":\"Springfield\"", json);
        Assert.Contains("\"PostalCode\":\"12345\"", json);
        Assert.Contains("\"Country\":\"US\"", json);

        var roundTripped = JsonSerializer.Deserialize<Modelable.Patient.PatientAddressV0>(json);
        Assert.NotNull(roundTripped);
        Assert.Equal(address, roundTripped);
    }
}