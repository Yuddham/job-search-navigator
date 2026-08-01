(() => {
  const DESIGN_WIDTH = 1200;

  function scaleFrames() {
    document.querySelectorAll(".frame-wrap").forEach((wrap) => {
      const iframe = wrap.querySelector("iframe");
      const scale = wrap.clientWidth / DESIGN_WIDTH;
      iframe.style.transform = `scale(${scale})`;
    });
  }

  window.addEventListener("resize", scaleFrames);
  window.addEventListener("load", scaleFrames);
  // Also run once immediately in case load already fired.
  scaleFrames();
  setTimeout(scaleFrames, 100);

  const gridEl = document.getElementById("grid");
  const fullViewEl = document.getElementById("fullView");
  const variantTabsEl = document.getElementById("variantTabs");
  const fullFrame = document.getElementById("fullFrame");

  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".mode-btn").forEach((b) => b.classList.toggle("active", b === btn));
      const mode = btn.dataset.mode;
      if (mode === "grid") {
        gridEl.classList.remove("hidden");
        fullViewEl.classList.remove("visible");
        variantTabsEl.classList.remove("visible");
        scaleFrames();
      } else {
        gridEl.classList.add("hidden");
        fullViewEl.classList.add("visible");
        variantTabsEl.classList.add("visible");
      }
    });
  });

  document.querySelectorAll(".variant-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".variant-tab-btn").forEach((b) => b.classList.toggle("active", b === btn));
      fullFrame.src = `${btn.dataset.variant}/hero.html`;
    });
  });

  document.querySelectorAll("[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const variant = btn.dataset.open;
      document.querySelector('.mode-btn[data-mode="full"]').click();
      document.querySelector(`.variant-tab-btn[data-variant="${variant}"]`).click();
    });
  });
})();
