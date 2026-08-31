const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function revealSections() {
  const sections = document.querySelectorAll(".reveal");
  if (reduceMotion || !("IntersectionObserver" in window)) {
    sections.forEach((section) => section.classList.add("is-visible"));
    return;
  }

  document.body.classList.add("can-reveal");
  requestAnimationFrame(() => {
    const first = document.querySelector(".hero.reveal");
    if (first) {
      first.classList.add("is-visible");
    }
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.18 }
  );

  sections.forEach((section) => observer.observe(section));
}

function markBrokenImages() {
  document.querySelectorAll("img").forEach((image) => {
    image.addEventListener("error", () => {
      const parent = image.closest("figure, article");
      if (parent) {
        parent.dataset.imageState = "unavailable";
        parent.setAttribute("aria-label", "图片暂不可用，页面内容仍可阅读");
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  revealSections();
  markBrokenImages();
});
