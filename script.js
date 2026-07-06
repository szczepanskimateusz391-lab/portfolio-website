const LINKEDIN_URL = "https://www.linkedin.com/in/mateusz-szczepanski-data/";

const lightbox = document.querySelector("#dashboard-lightbox");
const lightboxImage = lightbox?.querySelector("img");
const lightboxCaption = lightbox?.querySelector("figcaption");
const closeButton = lightbox?.querySelector(".lightbox-close");
let lastFocusedElement = null;

document.querySelectorAll("[data-linkedin-url]").forEach((link) => {
  link.href = LINKEDIN_URL;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
});

const structuredData = document.querySelector("#structured-data");
if (structuredData) {
  try {
    const schema = JSON.parse(structuredData.textContent);
    schema.sameAs = [LINKEDIN_URL];
    structuredData.textContent = JSON.stringify(schema);
  } catch (error) {
    console.warn("Could not update structured data LinkedIn URL.", error);
  }
}

function openLightbox(trigger) {
  if (!lightbox || !lightboxImage || !lightboxCaption) return;

  lastFocusedElement = document.activeElement;
  lightboxImage.src = trigger.dataset.full;
  lightboxImage.alt = trigger.querySelector("img")?.alt || "Powiększony screenshot projektu";
  lightboxCaption.textContent = trigger.dataset.title || "";
  lightbox.classList.add("is-open");
  lightbox.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  closeButton?.focus();
}

function closeLightbox() {
  if (!lightbox || !lightboxImage) return;

  lightbox.classList.remove("is-open");
  lightbox.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  lightboxImage.src = "";

  if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
    lastFocusedElement.focus();
  }
}

document.querySelectorAll(".lightbox-trigger").forEach((trigger) => {
  trigger.addEventListener("click", () => openLightbox(trigger));
});

closeButton?.addEventListener("click", closeLightbox);

lightbox?.addEventListener("click", (event) => {
  if (event.target === lightbox) {
    closeLightbox();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && lightbox?.classList.contains("is-open")) {
    closeLightbox();
  }
});
