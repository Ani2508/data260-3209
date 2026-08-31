// Closure to track successful submission count (II.5)
const makeCounter = () => {
  let count = 0;
  return () => ++count;
};
const incrementSubmissions = makeCounter();

const form = document.getElementById("trialForm");

// Arrow function validator (II.1)
const validateForm = () => {
  const content = document.getElementById("content").value;
  const termsChecked = document.getElementById("terms").checked;

  // II.1a: content must be more than 25 characters
  if (content.length <= 25) {
    alert("Trial Summary must be more than 25 characters.");
    return false;
  }

  // II.1b: terms checkbox must be checked
  if (!termsChecked) {
    alert("You must agree to the terms and conditions.");
    return false;
  }

  return true;
};

form.addEventListener("submit", (event) => {
  event.preventDefault(); // keep page from reloading so console output is visible

  if (!validateForm()) return;

  // Gather form data
  const formData = {
    trialTitle: document.getElementById("trialTitle").value,
    sponsor: document.getElementById("sponsor").value,
    email: document.getElementById("email").value,
    content: document.getElementById("content").value,
    status: document.getElementById("status").value,
  };

  // II.2: convert to JSON string and log
  const jsonString = JSON.stringify(formData);
  console.log("Form data as JSON string:", jsonString);

  // Parse back into an object to work with (II.3, II.4 operate on parsed object)
  const parsed = JSON.parse(jsonString);

  // II.3: object destructuring to extract primary field + email
  const { trialTitle, email } = parsed;
  console.log("Trial Title:", trialTitle);
  console.log("Email:", email);

  // II.4: spread operator to add submissionDate
  const updated = { ...parsed, submissionDate: new Date().toISOString() };
  console.log("Updated object with submissionDate:", updated);

  // II.5: closure tracks submission count
  const submissionCount = incrementSubmissions();
  console.log("Successful submission count:", submissionCount);
});
