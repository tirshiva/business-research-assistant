import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createInvestigation } from "../api";

export function NewInvestigationPage() {
  const navigate = useNavigate();
  const [businessType, setBusinessType] = useState("cloud kitchen");
  const [location, setLocation] = useState("Sector 62, Noida");
  const [targetCustomer, setTargetCustomer] = useState("office workers");
  const [budget, setBudget] = useState("");
  const [question, setQuestion] = useState(
    "Is Sector 62, Noida a good location for a cloud kitchen targeting office workers?",
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const created = await createInvestigation({
        research_question: question,
        business_type: businessType,
        location,
        target_customer: targetCustomer,
        budget,
      });
      navigate(`/investigations/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start research");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <div className="hero">
        <h2>Investigate a business location</h2>
        <p className="muted">
          Submit a real question. Specialized research agents gather public
          evidence, score the opportunity, and cite sources.
        </p>
      </div>
      <form className="form-card" onSubmit={onSubmit}>
        <div className="grid-2">
          <label>
            Business type
            <input
              value={businessType}
              onChange={(event) => setBusinessType(event.target.value)}
              required
              placeholder="cloud kitchen"
            />
          </label>
          <label>
            Location
            <input
              value={location}
              onChange={(event) => setLocation(event.target.value)}
              required
              placeholder="Sector 62, Noida"
            />
          </label>
          <label>
            Target customer
            <input
              value={targetCustomer}
              onChange={(event) => setTargetCustomer(event.target.value)}
              placeholder="office workers"
            />
          </label>
          <label>
            Budget
            <input
              value={budget}
              onChange={(event) => setBudget(event.target.value)}
              placeholder="₹15–20 lakh fit-out"
            />
          </label>
        </div>
        <label style={{ marginTop: "1rem" }}>
          Research question
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            required
          />
        </label>
        <div style={{ marginTop: "1.2rem" }}>
          <button type="submit" disabled={busy}>
            {busy ? "Starting…" : "Start investigation"}
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </form>
    </section>
  );
}
