package replay

import (
	"strings"
	"testing"
)

// Repair-loop visualization (v0.8, events schema 2). The fixture is a REAL
// fake-provider repair run: attempt 1 mismatched 70/85 cases, attempt 2
// received the mismatch evidence and verified 85/85 (provenance in
// testdata/runs/README.md).

func TestRepairSummaryCounts(t *testing.T) {
	sum, err := LoadRun(fixturesDir + "/accepted-repair-fake")
	if err != nil {
		t.Fatalf("LoadRun: %v", err)
	}
	if sum.Attempts != 2 {
		t.Fatalf("Attempts = %d, want 2", sum.Attempts)
	}
	if sum.Repairs != 1 {
		t.Fatalf("Repairs = %d, want 1", sum.Repairs)
	}
	if sum.LastRepairKind != "verify_mismatch" {
		t.Fatalf("LastRepairKind = %q, want verify_mismatch", sum.LastRepairKind)
	}
	if sum.Status != "accepted" {
		t.Fatalf("Status = %q, want accepted", sum.Status)
	}
}

func TestRepairFlowAndLog(t *testing.T) {
	if got := FlowNode("repair"); got != "generate" {
		t.Fatalf("FlowNode(repair) = %q, want generate", got)
	}
	sum, err := LoadRun(fixturesDir + "/accepted-repair-fake")
	if err != nil {
		t.Fatalf("LoadRun: %v", err)
	}
	var found bool
	for _, ln := range sum.Log {
		if strings.Contains(ln, "↻ repair · attempt 2 · evidence: mismatched cases") {
			found = true
		}
	}
	if !found {
		t.Fatalf("log has no repair line; log:\n%s", strings.Join(sum.Log, "\n"))
	}
	if !strings.Contains(attemptsCountLine(sum), "1 repair(s)") {
		t.Fatalf("attemptsCountLine = %q, want the repair count", attemptsCountLine(sum))
	}
	// runs without repairs render exactly as before
	noRep := &RunSummary{Attempts: 3}
	if got := attemptsCountLine(noRep); got != "attempts 3" {
		t.Fatalf("attemptsCountLine without repairs = %q, want 'attempts 3'", got)
	}
}

func TestRepairResultStrip(t *testing.T) {
	d := LoadResult(fixturesDir + "/accepted-repair-fake")
	if len(d.Attempts) != 2 {
		t.Fatalf("attempts = %d, want 2", len(d.Attempts))
	}
	if d.Attempts[0].Repair != "" {
		t.Fatalf("attempt 1 must carry no repair marker, got %q", d.Attempts[0].Repair)
	}
	if d.Attempts[1].Repair != "verify_mismatch" {
		t.Fatalf("attempt 2 Repair = %q, want verify_mismatch", d.Attempts[1].Repair)
	}
	lines := stripAttemptLines(d.Attempts[1])
	if !strings.Contains(lines[0], "↻ mismatch") {
		t.Fatalf("strip head lacks the repair marker: %q", lines[0])
	}
	if !strings.Contains(lines[0], "◆ accepted") {
		t.Fatalf("strip head lacks the outcome: %q", lines[0])
	}
	if got := attemptsLine(d); !strings.Contains(got, "accepted on attempt 2") || !strings.Contains(got, "1 repair(s)") {
		t.Fatalf("attemptsLine = %q, want accept + repair note", got)
	}
}

func TestRepairFromEventsOnly(t *testing.T) {
	// state.json-less fallback: the repair marker must survive reconstruction
	// from the event stream alone.
	sum, err := LoadRun(fixturesDir + "/accepted-repair-fake")
	if err != nil {
		t.Fatalf("LoadRun: %v", err)
	}
	atts := attemptsFromSummary(sum)
	if len(atts) != 2 {
		t.Fatalf("attemptsFromSummary len = %d, want 2", len(atts))
	}
	if atts[1].Repair != "verify_mismatch" {
		t.Fatalf("event-fallback Repair = %q, want verify_mismatch", atts[1].Repair)
	}
}

func TestRepairEvidenceLabels(t *testing.T) {
	cases := map[string]string{
		"verify_mismatch":  "mismatched cases",
		"build_error":      "compiler errors",
		"safety_violation": "safety findings",
		"no_gain":          "measured no-gain",
		"load_error":       "load failure",
		"future_kind":      "future_kind",
	}
	for kind, want := range cases {
		if got := repairEvidence(kind); got != want {
			t.Fatalf("repairEvidence(%q) = %q, want %q", kind, got, want)
		}
	}
}
