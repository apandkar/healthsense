const API_URL = "http://127.0.0.1:8000";

async function checkHealth() {

    const symptoms = document.getElementById("symptoms").value.trim();
    const location = document.getElementById("location").value.trim();

    const button = document.getElementById("checkButton");
    const loading = document.getElementById("loading");
    const error = document.getElementById("error");
    const results = document.getElementById("results");

    error.classList.add("hidden");
    results.classList.add("hidden");

    if (!symptoms) {
        showError("Please describe your symptoms.");
        return;
    }

    if (!location) {
        showError("Please enter your location.");
        return;
    }

    button.disabled = true;
    loading.classList.remove("hidden");

    try {

        const response = await fetch(`${API_URL}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                symptoms: symptoms,
                location: location
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "The healthcare service returned an error."
            );
        }

        displayResults(data);

    } catch (err) {

        console.error(err);

        showError(
            "Unable to connect to IKHealthSense API. " +
            "Make sure FastAPI is running on port 8000."
        );

    } finally {

        button.disabled = false;
        loading.classList.add("hidden");
    }
}


function displayResults(data) {

    const results = document.getElementById("results");

    let result = data.response || data.result || data;

    if (typeof result === "string") {

        document.getElementById("triageMessage").textContent = result;
        document.getElementById("urgency").textContent = "ASSESSMENT";
        document.getElementById("specialization").textContent =
            "Please review the response below.";

        document.getElementById("hospitals").innerHTML = "";
        document.getElementById("doctors").innerHTML = "";
        document.getElementById("appointments").innerHTML = "";

        results.classList.remove("hidden");
        return;
    }

    const triage = result.triage || {};

    document.getElementById("urgency").textContent =
        triage.urgency || "UNKNOWN";

    document.getElementById("triageMessage").textContent =
        triage.message || "";

    document.getElementById("specialization").textContent =
        result.specialization || "Not specified";

    displayEmergency(triage);

    displayHospitals(result.hospitals || []);

    displayDoctors(result.doctors || []);

    displayAppointments(result.appointments || []);

    results.classList.remove("hidden");
}


function displayEmergency(triage) {

    const alert = document.getElementById("emergencyAlert");
    const message = document.getElementById("emergencyMessage");

    if (
        triage.urgency &&
        triage.urgency.toUpperCase() === "EMERGENCY"
    ) {

        message.textContent =
            triage.message ||
            "Your symptoms may require immediate medical attention.";

        alert.classList.remove("hidden");

    } else {

        alert.classList.add("hidden");
    }
}


function displayHospitals(hospitals) {

    const container = document.getElementById("hospitals");

    if (!hospitals.length) {

        container.innerHTML =
            "<p>No matching hospitals were found.</p>";

        return;
    }

    container.innerHTML = hospitals.map(hospital => `

        <div class="hospital">

            <h4>${escapeHtml(
                hospital.hospital_name || "Hospital"
            )}</h4>

            <p>
                ${escapeHtml(
                    hospital.address || ""
                )}
            </p>

            <p>
                ${escapeHtml(
                    hospital.city || ""
                )}
                ${hospital.state ? ", " + escapeHtml(hospital.state) : ""}
                ${hospital.zip_code ? " " + escapeHtml(hospital.zip_code) : ""}
            </p>

        </div>

    `).join("");
}


function displayDoctors(doctors) {

    const container = document.getElementById("doctors");

    if (!doctors.length) {

        container.innerHTML =
            "<p>No matching doctors were found.</p>";

        return;
    }

    container.innerHTML = doctors.map(doctor => `

        <div class="doctor">

            <h4>${escapeHtml(
                doctor.name ||
                doctor.doctor_name ||
                "Doctor"
            )}</h4>

            <p>
                <strong>Specialization:</strong>
                ${escapeHtml(
                    doctor.specialization || ""
                )}
            </p>

            <p>
                <strong>Contact:</strong>
                ${escapeHtml(
                    doctor.contact || ""
                )}
            </p>

        </div>

    `).join("");
}


function displayAppointments(appointments) {

    const container = document.getElementById("appointments");

    if (!appointments.length) {

        container.innerHTML =
            "<p>No future appointments were found.</p>";

        return;
    }

    container.innerHTML = appointments.map(appointment => `

        <div class="appointment">

            <h4>
                ${escapeHtml(
                    appointment.doctor_name || "Doctor"
                )}
            </h4>

            <p>
                <strong>Specialization:</strong>
                ${escapeHtml(
                    appointment.specialization || ""
                )}
            </p>

            <p>
                <strong>Date & Time:</strong>
                ${formatDate(
                    appointment.appointment_datetime
                )}
            </p>

            <p>
                <strong>Contact:</strong>
                ${escapeHtml(
                    appointment.contact || ""
                )}
            </p>

            <p>
                <strong>Availability:</strong>
                ${appointment.available ? "Available" : "Not Available"}
            </p>

        </div>

    `).join("");
}


function formatDate(value) {

    if (!value) {
        return "Not specified";
    }

    const date = new Date(value);

    if (isNaN(date.getTime())) {
        return escapeHtml(String(value));
    }

    return date.toLocaleString(
        "en-IN",
        {
            dateStyle: "medium",
            timeStyle: "short"
        }
    );
}


function showError(message) {

    const error = document.getElementById("error");

    error.textContent = message;
    error.classList.remove("hidden");
}


function escapeHtml(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
