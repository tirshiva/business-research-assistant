import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { InvestigationPage } from "./pages/InvestigationPage";
import { NewInvestigationPage } from "./pages/NewInvestigation";

export function App() {
  return (
    <BrowserRouter>
      <div className="shell">
        <header className="brand">
          <div>
            <h1>
              <Link to="/" style={{ color: "inherit", textDecoration: "none" }}>
                India Business Research
              </Link>
            </h1>
            <p>Evidence-backed location and market investigations</p>
          </div>
        </header>
        <Routes>
          <Route path="/" element={<NewInvestigationPage />} />
          <Route
            path="/investigations/:id"
            element={<InvestigationPage />}
          />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
