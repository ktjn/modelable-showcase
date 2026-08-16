// Go probe for Modelable-generated types (IMPLEMENTATION_PLAN.md Task 7.4):
// build the generated Go value types with a real `go test` and exercise
// construction + JSON round-trips, not a text grep.
//
// The go target emits one file per model/projection under
// generated/go/<domain>/<name>.go, packaged as the lowercase domain name. Go
// compiles whole packages. Under the pinned 1.8.0 release, the patient and
// scheduling packages build cleanly - their value types, semantic types,
// models, and projections all resolve within the same package (UPSTREAM_FINDINGS.md
// #21/#22 fixed via #365) - as do the self-contained billing/clinical value
// type files. Cross-package references (billing/clinical/reporting referencing
// PatientPatientId, SchedulingPractitionerId, SchedulingTimeRangeV0) are still
// emitted bare with no import, so those packages still do not build (#31).
//
// This probe works around whole-package compilation without touching generated
// output: it copies the compilable subset verbatim into a throwaway module
// (the reassembly set below), then runs `go test` there. No generated file is
// edited or copied into git. The construction/serialization proof lives in the
// throwaway test program; tests/integration/test_go_codegen.py asserts the
// full-set failure explicitly so it flips when the emitter is fixed.
//
// Revisit once Modelable is re-pinned past a release that fixes #31: the full
// generated/go/ set should build in its original layout at that point.
package probe

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"testing"
)

// generatedSubset maps each verbatim generated source file (relative to
// generated/go/) to the throwaway-module package directory it is copied into.
// The whole patient and scheduling packages are copied, plus the
// self-contained billing/clinical value types. Kept in sync with
// tests/integration/test_go_codegen.py's expectations.
func generatedSubset() map[string]string {
	set := map[string]string{
		"billing/billing_invoice_line_v0.go": "billing",
		"clinical/clinical_diagnosis_v0.go":  "clinical",
	}
	genDir := filepath.Join(repoRoot(), "generated", "go")
	for _, pkg := range []string{"patient", "scheduling"} {
		entries, err := os.ReadDir(filepath.Join(genDir, pkg))
		if err != nil {
			continue
		}
		for _, entry := range entries {
			if !entry.IsDir() && filepath.Ext(entry.Name()) == ".go" {
				set[filepath.Join(pkg, entry.Name())] = pkg
			}
		}
	}
	return set
}

// tempTestProgram is written into the throwaway module and exercises the
// reassembled value types with construction + JSON round-trips. It must stay
// valid standalone Go (no external dependencies, stdlib only).
const tempTestProgram = `package probe

import (
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"probe/billing"
	"probe/clinical"
	"probe/patient"
	"probe/scheduling"
)

func TestGeneratedValueTypesConstructAndSerialize(t *testing.T) {
	address := patient.PatientAddressV0{
		Street: "1 Main", City: "Springfield", PostalCode: "12345", Country: "US",
	}
	assertRoundTrip(t, address)

	email := "ada@example.com"
	contact := patient.PatientContactDetailsV0{Email: &email}
	assertRoundTrip(t, contact)

	slot := scheduling.SchedulingTimeRangeV0{
		Start: time.Date(2026, 1, 1, 9, 0, 0, 0, time.UTC),
		End:   time.Date(2026, 1, 1, 17, 0, 0, 0, time.UTC),
	}
	assertRoundTrip(t, slot)

	line := billing.BillingInvoiceLineV0{
		Description: "clinic visit", Quantity: 2, UnitPrice: "10.50", LineTotal: "21.00",
	}
	assertRoundTrip(t, line)

	severity := int64(2)
	diagnosis := clinical.ClinicalDiagnosisV0{
		Codes:         []string{"R10"},
		DiagnosedDate: time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
		Description:   &email,
		SeverityRank:  &severity,
	}
	assertRoundTrip(t, diagnosis)
}

func assertRoundTrip[T any](t *testing.T, in T) {
	t.Helper()
	data, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal %T: %v", in, err)
	}
	var out T
	if err := json.Unmarshal(data, &out); err != nil {
		t.Fatalf("unmarshal %T: %v", in, err)
	}
	if !reflect.DeepEqual(in, out) {
		t.Fatalf("round trip mismatch:\n  in:  %#v\n  out: %#v", in, out)
	}
}
`

func TestGeneratedValueTypes(t *testing.T) {
	goBin, err := exec.LookPath("go")
	if err != nil {
		t.Skip("go toolchain not on PATH")
	}

	genDir := filepath.Join(repoRoot(), "generated", "go")
	if _, err := os.Stat(genDir); err != nil {
		t.Fatalf("run 'make generate' first (generated/go missing): %v", err)
	}

	tmp := t.TempDir()
	if err := os.WriteFile(filepath.Join(tmp, "go.mod"), []byte("module probe\n\ngo 1.26\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	// Reassemble the compilable subset into per-domain packages (see the header
	// comment). Files are copied verbatim, never edited.
	set := generatedSubset()
	rels := make([]string, 0, len(set))
	for rel := range set {
		rels = append(rels, rel)
	}
	sort.Strings(rels)
	for _, rel := range rels {
		data, err := os.ReadFile(filepath.Join(genDir, filepath.FromSlash(rel)))
		if err != nil {
			t.Fatalf("read generated file %s: %v", rel, err)
		}
		dstDir := filepath.Join(tmp, set[rel])
		if err := os.MkdirAll(dstDir, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dstDir, filepath.Base(rel)), data, 0o644); err != nil {
			t.Fatal(err)
		}
	}

	if err := os.WriteFile(filepath.Join(tmp, "generated_probe_test.go"), []byte(tempTestProgram), 0o644); err != nil {
		t.Fatal(err)
	}

	cmd := exec.Command(goBin, "test", "./...")
	cmd.Dir = tmp
	cmd.Env = append(os.Environ(), "GOTOOLCHAIN=local")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go test on reassembled generated value types failed:\n%s", out)
	}
}

// repoRoot returns the showcase repository root (two levels above probes/go).
func repoRoot() string {
	_, file, _, _ := runtime.Caller(0)
	return filepath.Dir(filepath.Dir(filepath.Dir(file)))
}