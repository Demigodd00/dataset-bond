const dimensions = ["Schema", "Completeness", "Annotation", "Consistency", "Provenance"];
const values = Object.fromEntries(dimensions.map((name) => [name, "PASS"]));
const controls = document.querySelector("#dimension-controls");

for (const name of dimensions) {
  const row = document.createElement("div");
  row.className = "dimension";
  const label = document.createElement("label");
  label.textContent = name;
  const segmented = document.createElement("div");
  segmented.className = "segmented";
  for (const option of ["PASS", "FAIL", "UNCLEAR"]) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = option;
    button.className = option === "PASS" ? "active" : "";
    button.addEventListener("click", () => {
      values[name] = option;
      segmented.querySelectorAll("button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderOutcome();
    });
    segmented.append(button);
  }
  row.append(label, segmented);
  controls.append(row);
}

function deriveOutcome() {
  if (values.Schema === "FAIL" || values.Provenance === "FAIL") {
    return ["REJECT", "Schema or provenance failed the contract's hard boundary. Buyer refund: 100%."];
  }
  const labels = Object.values(values);
  const passes = labels.filter((value) => value === "PASS").length;
  if (passes === 5) return ["ACCEPT", "All five dimensions pass. Provider payout: 100%."];
  if (labels.includes("UNCLEAR")) return ["REVISION REQUIRED", "Ambiguity invokes the one bounded revision before any payout."];
  if (passes >= 3) return ["PARTIAL ACCEPT", "Three or four dimensions pass. Example provider payout: 60%."];
  return ["REJECT", "The evidence does not meet enough frozen dimensions. Buyer refund: 100%."];
}

function renderOutcome() {
  const [outcome, detail] = deriveOutcome();
  document.querySelector("#policy-result").textContent = outcome;
  document.querySelector("#policy-detail").textContent = detail;
}

async function loadDeployment() {
  try {
    const response = await fetch("../deployments/studionet.json", { cache: "no-store" });
    if (!response.ok) return;
    const deployment = await response.json();
    const pending = [deployment.registry.address, deployment.job.address, deployment.commit].includes("PENDING");
    document.querySelector("#registry-address").textContent = deployment.registry.address;
    document.querySelector("#job-address").textContent = deployment.job.address;
    document.querySelector("#commit-hash").textContent = deployment.commit;
    document.querySelector("#deployment-status").textContent = pending
      ? "StudioNet deployment has not yet been published."
      : `Verified on chain ${deployment.chain_id}; final outcome: ${deployment.smoke_test.observed_final_outcome}.`;
  } catch (_) {
    // The page remains useful when opened directly from disk.
  }
}

renderOutcome();
loadDeployment();

