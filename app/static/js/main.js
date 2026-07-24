/* Drag-and-drop preview + submit progress bar for the upload pages, and a
 * small Chart.js wrapper for the Statistics dashboard.
 */
window.ImageStorageDemo = (function () {
  function initUploadPage(opts) {
    const dropZone = document.getElementById(opts.dropZoneId);
    const input = document.getElementById(opts.inputId);
    const preview = document.getElementById(opts.previewId);
    const form = document.getElementById(opts.formId);
    const progressWrap = document.getElementById(opts.progressWrapId);
    const progressBar = document.getElementById(opts.progressBarId);
    if (!dropZone || !input) return;

    dropZone.addEventListener("click", () => input.click());

    ["dragenter", "dragover"].forEach((evt) =>
      dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
      })
    );
    dropZone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        showPreview();
      }
    });

    input.addEventListener("change", showPreview);

    function showPreview() {
      const file = input.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (e) => {
        preview.src = e.target.result;
        preview.classList.remove("d-none");
      };
      reader.readAsDataURL(file);
    }

    if (form) {
      form.addEventListener("submit", (e) => {
        if (!input.files.length) return;
        e.preventDefault();

        const formData = new FormData(form);
        const xhr = new XMLHttpRequest();
        xhr.open("POST", form.action || window.location.href);

        progressWrap.classList.remove("d-none");
        xhr.upload.addEventListener("progress", (evt) => {
          if (evt.lengthComputable) {
            const pct = Math.round((evt.loaded / evt.total) * 100);
            progressBar.style.width = pct + "%";
            progressBar.textContent = pct + "%";
          }
        });
        // On success the server redirects to /gallery; xhr follows that
        // transparently and responseURL reflects the final page, so we can
        // just navigate there. On validation failure the server re-renders
        // this same upload page (with flash/form errors) without a
        // redirect, so responseURL is unchanged -- render that HTML in
        // place instead of navigating, or the flash message would be lost.
        xhr.onload = () => {
          const currentUrl = window.location.href.split("#")[0];
          if (xhr.responseURL && xhr.responseURL !== currentUrl) {
            window.location.href = xhr.responseURL;
          } else {
            document.open();
            document.write(xhr.responseText);
            document.close();
          }
        };
        xhr.onerror = () => {
          progressWrap.classList.add("d-none");
          form.submit();
        };
        xhr.send(formData);
      });
    }
  }

  function renderStorageChart(canvasId, counts) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") return;
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["File System", "Database BLOB"],
        datasets: [
          {
            data: [counts.filesystem, counts.blob],
            backgroundColor: ["#0d6efd", "#198754"],
          },
        ],
      },
      options: { responsive: true },
    });
  }

  return { initUploadPage, renderStorageChart };
})();
