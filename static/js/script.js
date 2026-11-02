
document.addEventListener("DOMContentLoaded", () => {
    // Highlight the navigation link for the current page.
    const currentPath = window.location.pathname;

    document.querySelectorAll(".sidebar nav a").forEach(link => {
        const linkPath = new URL(link.href).pathname;

        if (linkPath === currentPath) {
            link.style.background = "#17152b";
            link.style.color = "#00e5ff";
            link.style.borderColor = "#00e5ff50";
        }
    });

    // Confirm before submitting the student registration form.
    const registrationForm = document.querySelector(
        'form[action*="register"]'
    );

    if (registrationForm) {
        registrationForm.addEventListener("submit", event => {
            const fileInput = registrationForm.querySelector(
                'input[type="file"]'
            );

            if (!fileInput || !fileInput.files.length) {
                event.preventDefault();
                alert("Please select a student photo.");
            }
        });
    }
});
