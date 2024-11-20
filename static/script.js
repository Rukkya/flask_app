// Toggle visibility of the document upload form based on login/signup flow
document.addEventListener("DOMContentLoaded", function () {
    const uploadForm = document.getElementById("upload-form");
    const queryForm = document.getElementById("query-form");

    // Only show the upload and query form once the user is logged in
    if (sessionStorage.getItem('user_id')) {
        uploadForm.style.display = "block";
        queryForm.style.display = "block";
    }
});
