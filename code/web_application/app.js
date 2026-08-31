// ---- Closure: tracks how many successful submissions have happened (II.5) ----
const makeCounter = () => {
  let count = 0;                 // private, only reachable via the returned fn
  return () => ++count;
};
const incrementSubmissions = makeCounter();

// ---- Element refs ----
const form = document.getElementById("trialForm");
const contentEl = document.getElementById("content");
const counterEl = document.getElementById("counter");
const trialList = document.getElementById("trialList");
const countBadge = document.getElementById("countBadge");
const sideEmpty = document.getElementById("sideEmpty");

// ---- Live character counter on the summary (interactive polish; reflects the >25 rule) ----
contentEl.addEventListener("input", () => {
  const n = contentEl.value.length;
  counterEl.textContent = n > 25
    ? `${n} characters \u2014 looks good`
    : `${n} characters \u2014 need more than 25`;
  counterEl.classList.toggle("ok", n > 25);
});

// ---- Small helper to show/clear an inline error under a field ----
const setError = (id, msg) => { document.getElementById("err-" + id).textContent = msg || ""; };
const clearErrors = () => ["trialTitle","sponsor","email","content","terms"].forEach(id => setError(id, ""));

// ---- Arrow function validator (II.1) ----
// Keeps required alert() AND adds inline messages.
const validateForm = () => {
  clearErrors();
  const content = contentEl.value;
  const termsChecked = document.getElementById("terms").checked;

  // II.1a: content must be MORE than 25 characters
  if (content.length <= 25) {
    alert("Trial Summary must be more than 25 characters.");
    setError("content", "Please enter more than 25 characters.");
    return false;
  }
  // II.1b: terms checkbox must be checked
  if (!termsChecked) {
    alert("You must agree to the terms and conditions.");
    setError("terms", "You must agree before submitting.");
    return false;
  }
  return true;
};

// ---- Map status -> pill CSS class (domain logic, not decoration) ----
const statusClass = (status) => {
  if (status.startsWith("Recruiting")) return "recruiting";
  if (status.startsWith("Active"))     return "active";
  if (status.startsWith("Completed"))  return "completed";
  return "terminated";
};

// ---- Render one submitted trial into the sidebar ----
const addTrialToList = (trial, count) => {
  sideEmpty.style.display = "none";
  const li = document.createElement("li");
  li.className = "trial-item";
  li.innerHTML =
    `<h3>${trial.trialTitle}</h3>` +
    `<p class="tspon">${trial.sponsor}</p>` +
    `<span class="pill ${statusClass(trial.status)}">${trial.status}</span>`;
  trialList.prepend(li);
  countBadge.textContent = count;
};

// ---- Submit handler ----
form.addEventListener("submit", (event) => {
  event.preventDefault();               // stop reload so console output persists
  if (!validateForm()) return;

  // Collect field values
  const formData = {
    trialTitle: document.getElementById("trialTitle").value,
    sponsor: document.getElementById("sponsor").value,
    email: document.getElementById("email").value,
    content: contentEl.value,
    status: document.getElementById("status").value,
  };

  // II.2: convert to JSON string and log
  const jsonString = JSON.stringify(formData);
  console.log("Form data as JSON string:", jsonString);

  // Parse back for the next operations
  const parsed = JSON.parse(jsonString);

  // II.3: object destructuring — pull primary field + email
  const { trialTitle, email } = parsed;
  console.log("Trial Title:", trialTitle);
  console.log("Email:", email);

  // II.4: spread operator — copy + add submissionDate
  const updated = { ...parsed, submissionDate: new Date().toISOString() };
  console.log("Updated object with submissionDate:", updated);

  // II.5: closure — increment + log count
  const submissionCount = incrementSubmissions();
  console.log("Successful submission count:", submissionCount);

  // Interactive: show it in the sidebar and reset the form
  addTrialToList(updated, submissionCount);
  form.reset();
  counterEl.textContent = "0 characters \u2014 need more than 25";
  counterEl.classList.remove("ok");
  document.getElementById("trialTitle").focus();
});
