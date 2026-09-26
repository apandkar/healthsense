const API_URL = "/chat";
const BOOK_API_URL = "/appointments/book";

const symptomsInput = document.getElementById("symptoms");
const locationInput = document.getElementById("location");
const checkButton = document.getElementById("checkHealthcare");
const loading = document.getElementById("loading");
const responseContainer = document.getElementById("response");

checkButton.addEventListener("click", checkHealthcare);


// ============================================================
// CHECK HEALTHCARE
// ============================================================

async function checkHealthcare() {

    const symptoms = symptomsInput.value.trim();
    const location = locationInput.value.trim();

    if (!symptoms) {
        alert("Please describe your symptoms.");
        symptomsInput.focus();
        return;
    }

    if (!location) {
        alert("Please enter your location.");
        locationInput.focus();
        return;
    }

    loading.style.display = "flex";
    responseContainer.innerHTML = "";
    checkButton.disabled = true;

    try {

        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                symptoms: symptoms,
                location: location
            })
        });

        if (!response.ok) {
            throw new Error(
                "API request failed. HTTP status: " + response.status
            );
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(
                data.detail || "Unable to process healthcare request."
            );
        }

        renderHealthcareResult(data.response);

    } catch (error) {

        console.error("IKHealthSense Error:", error);

        responseContainer.innerHTML = `
            <div class="error-box">
                <h2>Unable to connect</h2>
                <p>${escapeHtml(error.message)}</p>
                <p>
                    Please make sure the IKHealthSense API
                    is running on port 8000.
                </p>
            </div>
        `;

    } finally {

        loading.style.display = "none";
        checkButton.disabled = false;
    }
}


// ============================================================
// RENDER HEALTHCARE RESULT
// ============================================================

function renderHealthcareResult(result) {

    if (!result) {

        responseContainer.innerHTML = `
            <div class="error-box">
                <h2>No result received</h2>
                <p>The healthcare service returned an empty response.</p>
            </div>
        `;

        return;
    }

    let html = "";

    // ============================================================
    // TRIAGE
    // ============================================================

    const urgency = result.triage?.urgency || "UNKNOWN";

    const triageMessage =
        result.triage?.message ||
        "Please consult a healthcare professional.";

    if (urgency === "EMERGENCY") {

        html += `
            <div class="emergency-box">
                <h2>EMERGENCY</h2>

                <p>
                    ${escapeHtml(triageMessage)}
                </p>

                <strong>
                    Please seek immediate emergency medical care.
                </strong>
            </div>
        `;

    } else {

        html += `
            <div class="triage-box">
                <h2>Health Assessment</h2>

                <p>
                    <strong>Urgency:</strong>
                    ${escapeHtml(urgency)}
                </p>

                <p>
                    ${escapeHtml(triageMessage)}
                </p>
            </div>
        `;
    }


    // ============================================================
    // SPECIALIZATION
    // ============================================================

    if (result.specialization) {

        html += `
            <div class="section-card">

                <h2>Recommended Specialist</h2>

                <div class="specialist-name">
                    ${escapeHtml(result.specialization)}
                </div>

            </div>
        `;
    }


    // ============================================================
    // HOSPITALS
    // ============================================================

    html += `
        <div class="section-card">

            <h2>Emergency Hospitals</h2>
    `;

    if (result.hospitals && result.hospitals.length > 0) {

        html += `<div class="hospital-grid">`;

        result.hospitals.forEach((hospital) => {

            html += `
                <div class="hospital-card">

                    <h3>
                        ${escapeHtml(
                            hospital.hospital_name || "Hospital"
                        )}
                    </h3>

                    <p>
                        <strong>Address:</strong><br>
                        ${escapeHtml(
                            hospital.address || "Not available"
                        )}
                    </p>

                    <p>
                        <strong>Location:</strong>
                        ${escapeHtml(hospital.city || "")},
                        ${escapeHtml(hospital.state || "")}
                        ${escapeHtml(hospital.zip_code || "")}
                    </p>

                    <p>
                        <strong>Phone:</strong>
                        ${escapeHtml(
                            hospital.phone_number || "Not available"
                        )}
                    </p>

                    <p>
                        <strong>Rating:</strong>
                        ${escapeHtml(
                            hospital.rating || "Not available"
                        )}
                    </p>

                </div>
            `;
        });

        html += `</div>`;

    } else {

        html += `
            <div class="empty-box">
                No emergency hospitals were found for
                ${escapeHtml(result.location || "this location")}.
            </div>
        `;
    }

    html += `</div>`;


    // ============================================================
    // DOCTORS
    // ============================================================

    html += `
        <div class="section-card">

            <h2>Recommended Doctors</h2>
    `;

    if (result.doctors && result.doctors.length > 0) {

        const uniqueDoctors = [];
        const seen = new Set();

        result.doctors.forEach((doctor) => {

            const key =
                `${doctor.name}|${doctor.specialization}|${doctor.contact}`;

            if (!seen.has(key)) {

                seen.add(key);
                uniqueDoctors.push(doctor);
            }
        });

        html += `<div class="doctor-grid">`;

        uniqueDoctors.forEach((doctor) => {

            html += `
                <div class="doctor-card">

                    <h3>
                        ${escapeHtml(
                            doctor.name || "Doctor"
                        )}
                    </h3>

                    <p>
                        <strong>Specialization:</strong>
                        ${escapeHtml(
                            doctor.specialization || ""
                        )}
                    </p>

                    <p>
                        <strong>Contact:</strong>
                        ${escapeHtml(
                            doctor.contact || "Not available"
                        )}
                    </p>

                </div>
            `;
        });

        html += `</div>`;

    } else {

        html += `
            <div class="empty-box">
                No doctors were found.
            </div>
        `;
    }

    html += `</div>`;


    // ============================================================
    // APPOINTMENTS
    // ============================================================

    html += `
        <div class="section-card">

            <h2>Available Appointments</h2>
    `;

    if (result.appointments && result.appointments.length > 0) {

        html += `<div class="appointment-grid">`;

        result.appointments.forEach((appointment, index) => {

            const slotId = appointment.slot_id;

            html += `
                <div class="appointment-card"
                     id="appointment-${escapeHtml(slotId ?? index)}">

                    <h3>
                        ${escapeHtml(
                            appointment.doctor_name || "Doctor"
                        )}
                    </h3>

                    <p>
                        <strong>Specialization:</strong>
                        ${escapeHtml(
                            appointment.specialization || ""
                        )}
                    </p>

                    <p>
                        <strong>Date & Time:</strong><br>
                        ${escapeHtml(
                            formatDateTime(
                                appointment.appointment_datetime
                            )
                        )}
                    </p>

                    <p>
                        <strong>Contact:</strong>
                        ${escapeHtml(
                            appointment.contact || "Not available"
                        )}
                    </p>

                    <div class="available-badge">
                        Available
                    </div>

                    ${
                        slotId !== undefined && slotId !== null
                        ? `
                            <button
                                class="book-button"
                                onclick="bookAppointment(${Number(slotId)}, this)"
                            >
                                Book Appointment
                            </button>
                          `
                        : `
                            <div class="empty-box">
                                Booking ID unavailable.
                            </div>
                          `
                    }

                </div>
            `;
        });

        html += `</div>`;

    } else {

        html += `
            <div class="empty-box">
                No future appointments are currently available.
            </div>
        `;
    }

    html += `</div>`;


    // ============================================================
    // DISCLAIMER
    // ============================================================

    html += `
        <div class="disclaimer-box">

            <strong>Important Medical Disclaimer</strong>

            <p>
                ${escapeHtml(
                    result.disclaimer ||
                    "IKHealthSense provides healthcare navigation information and does not provide a medical diagnosis."
                )}
            </p>

        </div>
    `;

    responseContainer.innerHTML = html;
}


// ============================================================
// BOOK APPOINTMENT
// ============================================================

async function bookAppointment(slotId, button) {

    if (slotId === null || slotId === undefined || Number.isNaN(Number(slotId))) {
        alert("Invalid appointment slot.");
        return;
    }

    const confirmed = confirm(
        "Are you sure you want to book this appointment?"
    );

    if (!confirmed) {
        return;
    }

    const originalText = button.innerText;

    button.disabled = true;
    button.innerText = "Booking...";

    try {

        const response = await fetch(BOOK_API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                slot_id: Number(slotId)
            })
        });

        const data = await response.json();

        if (!response.ok) {

            throw new Error(
                data.detail || "Unable to book appointment."
            );
        }

        if (!data.success) {

            throw new Error(
                data.message || "Appointment booking failed."
            );
        }

        showBookingSuccess(data, button);

    } catch (error) {

        console.error("Booking Error:", error);

        alert(
            "Unable to book appointment.\n\n" +
            error.message
        );

        button.disabled = false;
        button.innerText = originalText;
    }
}


// ============================================================
// BOOKING SUCCESS
// ============================================================

function showBookingSuccess(data, button) {

    const card = button.closest(".appointment-card");

    if (!card) {
        return;
    }

    button.remove();

    const badge = card.querySelector(".available-badge");

    if (badge) {
        badge.remove();
    }

    const successBox = document.createElement("div");

    successBox.className = "booking-success";

    const appointment =
        data.appointment || {};

    successBox.innerHTML = `
        <strong>✓ Appointment Booked</strong>

        <p>
            ${escapeHtml(
                appointment.doctor_name || "Doctor"
            )}
        </p>

        <p>
            ${escapeHtml(
                formatDateTime(
                    appointment.appointment_datetime
                )
            )}
        </p>

        <p>
            Please keep this appointment information
            for your records.
        </p>
    `;

    card.appendChild(successBox);
}


// ============================================================
// DATE FORMAT
// ============================================================

function formatDateTime(value) {

    if (!value) {
        return "Not available";
    }

    const date = new Date(
        String(value).replace(" ", "T")
    );

    if (isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString([], {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}


// ============================================================
// HTML SECURITY
// ============================================================

function escapeHtml(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
