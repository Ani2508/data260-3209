// ---- Closure: counts successful submissions ----
const makeCounter = () => {
  let count = 0;
  return () => ++count;
};

const incrementSubmissions = makeCounter();

// ---- Element references ----
const form = document.getElementById("trialForm");
const contentEl = document.getElementById("content");
const counterEl = document.getElementById("counter");
const trialList = document.getElementById("trialList");
const countBadge = document.getElementById("countBadge");
const sideEmpty = document.getElementById("sideEmpty");
const loadingState = document.getElementById("loadingState");
const errorState = document.getElementById("errorState");
const updateTrialForm = document.getElementById("updateTrialForm");
const updateTitleEl = document.getElementById("updateTitle");
const updateSponsorEl = document.getElementById("updateSponsor");
const searchTrialForm = document.getElementById("searchTrialForm");
const searchInput = document.getElementById("searchInput");
const clearSearchBtn = document.getElementById("clearSearchBtn");

// ---- Display list states ----
const showListState = (state) => {
  loadingState.hidden = state !== "loading";
  errorState.hidden = state !== "error";
  sideEmpty.hidden = state !== "empty";
  trialList.hidden = state !== "list";
};

// ---- Character counter ----
contentEl.addEventListener("input", () => {
  const numberOfCharacters = contentEl.value.length;

  counterEl.textContent = numberOfCharacters > 25
    ? `${numberOfCharacters} characters — looks good`
    : `${numberOfCharacters} characters — need more than 25`;

  counterEl.classList.toggle(
    "ok",
    numberOfCharacters > 25
  );
});

// ---- Error helpers ----
const setError = (id, message) => {
  document.getElementById(`err-${id}`).textContent = message || "";
};

const clearErrors = () => {
  ["trialTitle", "sponsor", "email", "content", "terms"]
    .forEach(id => setError(id, ""));
};

// ---- Form validation ----
const validateForm = () => {
  clearErrors();

  const title = document.getElementById("trialTitle").value.trim();
  const sponsor = document.getElementById("sponsor").value.trim();
  const email = document.getElementById("email").value.trim();
  const content = contentEl.value.trim();
  const termsChecked = document.getElementById("terms").checked;

  if (!title) {
    setError("trialTitle", "Trial Title is required.");
    return false;
  }

  if (!sponsor) {
    setError("sponsor", "Sponsor / Institution is required.");
    return false;
  }

  if (!email) {
    setError("email", "Submitter Email is required.");
    return false;
  }

  if (content.length <= 25) {
    alert("Trial Summary must be more than 25 characters.");
    setError("content", "Please enter more than 25 characters.");
    return false;
  }

  if (!termsChecked) {
    alert("You must agree to the terms and conditions.");
    setError("terms", "You must agree before submitting.");
    return false;
  }

  return true;
};

// ---- Status CSS class ----
const statusClass = (status) => {
  if (status.startsWith("Recruiting")) return "recruiting";
  if (status.startsWith("Active")) return "active";
  if (status.startsWith("Completed")) return "completed";
  return "terminated";
};

// ---- Create one trial list item ----
const createTrialItem = (trial) => {
  const li = document.createElement("li");
  li.className = "trial-item";

  const title = document.createElement("h3");
  title.textContent = trial.trialTitle;

  const sponsor = document.createElement("p");
  sponsor.className = "tspon";
  sponsor.textContent = trial.sponsor;

  const status = document.createElement("span");
  status.className = `pill ${statusClass(trial.status)}`;
  status.textContent = trial.status;

  li.append(title, sponsor, status);

  return li;
};

// ---- Render all trials from FastAPI ----
const renderTrials = (trials) => {
  trialList.replaceChildren();
  countBadge.textContent = trials.length;

  if (trials.length === 0) {
    showListState("empty");
    return;
  }

  trials.forEach(trial => {
    trialList.appendChild(createTrialItem(trial));
  });

  showListState("list");
};

// ---- Load trials from FastAPI ----
const loadTrials = async () => {
  showListState("loading");

  try {
    const response = await fetch("/api/trials");

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    const trials = await response.json();
    renderTrials(trials);
  } catch (error) {
    console.error("Unable to load trials:", error);
    showListState("error");
  }
};

// ---- Submit a new trial to FastAPI ----
form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!validateForm()) {
    return;
  }

  showListState("loading");

  const trialData = {
    trialTitle: document.getElementById("trialTitle").value.trim(),
    sponsor: document.getElementById("sponsor").value.trim(),
    email: document.getElementById("email").value.trim(),
    content: contentEl.value.trim(),
    status: document.getElementById("status").value
  };

  try {
    const response = await fetch("/api/trials", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(trialData)
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    console.log("New trial added:", trialData);

    // FastAPI redirects to the home route.
    // Reloading displays the updated list from the backend.
    window.location.href = "/";
  } catch (error) {
    console.error("Unable to add trial:", error);
    showListState("error");
  }
});
// ---- Update trial ID 1 ----
updateTrialForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const updatedTrial = {
    trialTitle: updateTitleEl.value.trim(),
    sponsor: updateSponsorEl.value.trim()
  };

  if (!updatedTrial.trialTitle || !updatedTrial.sponsor) {
    alert("Both updated fields are required.");
    return;
  }

  try {
    const response = await fetch("/api/trials/1", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(updatedTrial)
    });

    if (!response.ok) {
      throw new Error(`Update failed with status ${response.status}`);
    }

    window.location.href = "/";
  } catch (error) {
    console.error("Unable to update trial:", error);
    showListState("error");
  }
});

// ---- Search trials by title or sponsor ----
const searchTrials = async (searchText) => {
  showListState("loading");

  try {
    const response = await fetch(
      `/api/trials/search?q=${encodeURIComponent(searchText)}`
    );

    if (!response.ok) {
      throw new Error(`Search failed with status ${response.status}`);
    }

    const matchingTrials = await response.json();
    renderTrials(matchingTrials);
  } catch (error) {
    console.error("Unable to search trials:", error);
    showListState("error");
  }
};

searchTrialForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const searchText = searchInput.value.trim();
  searchTrials(searchText);
});

clearSearchBtn.addEventListener("click", () => {
  searchInput.value = "";
  loadTrials();
});
// ---- Load records when the page opens ----
loadTrials();